#!/usr/bin/env python3
"""Run the old-android PAC resolver in its own utility process.

The VMOS compatibility build keeps renderers in the browser process. Android
normally hosts the V8 PAC resolver in that same browser process, where it has
crashed on affected Android 9 builds. Route only ProxyResolverFactory through
the existing sandboxed utility-process path.
"""
import os
import sys


FACTORY = "chrome/browser/net/chrome_mojo_proxy_resolver_factory.cc"
FACTORY_INCLUDES_OLD = """#if BUILDFLAG(IS_ANDROID)
#include "services/proxy_resolver/proxy_resolver_factory_impl.h"  // nogncheck crbug.com/40147906
#else
#include "content/public/browser/service_process_host.h"
#include "services/strings/grit/services_strings.h"
#endif
"""
FACTORY_INCLUDES_NEW = """#include "content/public/browser/service_process_host.h"
"""
FACTORY_ANDROID_OLD = """#if BUILDFLAG(IS_ANDROID)
    // For Android we just lazily initialize a single factory instance and keep
    // it around forever.
    static base::NoDestructor<proxy_resolver::ProxyResolverFactoryImpl> factory(
        remote->BindNewPipeAndPassReceiver());
#else
    // For other platforms we launch the resolver in its own sandboxed service
    // process.
    content::ServiceProcessHost::Launch(
        remote->BindNewPipeAndPassReceiver(),
        content::ServiceProcessHost::Options()
            .WithDisplayName(IDS_PROXY_RESOLVER_DISPLAY_NAME)
            .Pass());

    // The service will report itself idle once there are no more bound
    // ProxyResolver instances. We drop the Remote at that point to initiate
    // service process termination. Any subsequent call to
    // |GetProxyResolverFactory()| will launch a new process.
    remote->reset_on_idle_timeout(base::TimeDelta());

    // Also reset on disconnection in case, e.g., the service crashes.
    remote->reset_on_disconnect();
#endif
"""
FACTORY_ANDROID_NEW = """    // Helium: run PAC evaluation in a sandboxed utility process on Android.
    content::ServiceProcessHost::Launch(
        remote->BindNewPipeAndPassReceiver(),
        content::ServiceProcessHost::Options()
            .WithDisplayName("Proxy Resolver")
            .Pass());

    remote->reset_on_idle_timeout(base::TimeDelta());
    remote->reset_on_disconnect();
"""
FACTORY_MARKER = "Helium: run PAC evaluation in a sandboxed utility process on Android."

NETWORK = "chrome/browser/net/system_network_context_manager.cc"
NETWORK_OLD = """  if (!command_line.HasSwitch(switches::kWinHttpProxyResolver)) {
    if (command_line.HasSwitch(switches::kSingleProcess)) {
      LOG(ERROR) << "Cannot use V8 Proxy resolver in single process mode.";
    } else {
      network_context_params->proxy_resolver_factory =
          ChromeMojoProxyResolverFactory::CreateWithSelfOwnedReceiver();

#if BUILDFLAG(IS_CHROMEOS)
      network_context_params->dhcp_wpad_url_client =
          ash::DhcpWpadUrlClient::CreateWithSelfOwnedReceiver();
#endif  // BUILDFLAG(IS_CHROMEOS)
    }
  }
"""
NETWORK_NEW = """  // Helium: the PAC resolver runs in a dedicated utility process.
  if (!command_line.HasSwitch(switches::kWinHttpProxyResolver)) {
    network_context_params->proxy_resolver_factory =
        ChromeMojoProxyResolverFactory::CreateWithSelfOwnedReceiver();

#if BUILDFLAG(IS_CHROMEOS)
    network_context_params->dhcp_wpad_url_client =
        ash::DhcpWpadUrlClient::CreateWithSelfOwnedReceiver();
#endif  // BUILDFLAG(IS_CHROMEOS)
  }
"""
NETWORK_MARKER = "Helium: the PAC resolver runs in a dedicated utility process."

UTILITY = "content/browser/service_host/utility_process_host.cc"
UTILITY_INCLUDE_OLD = '#include "content/browser/service_host/utility_process_host.h"\n'
UTILITY_INCLUDE_NEW = (
    UTILITY_INCLUDE_OLD
    + '#include "services/proxy_resolver/public/mojom/proxy_resolver.mojom.h"\n'
)
UTILITY_OLD = """  if (RenderProcessHost::run_renderer_in_process()) {
    CHECK(g_utility_main_thread_factory, base::NotFatalUntil::M159);
"""
UTILITY_NEW = """  // Helium: only PAC resolution escapes renderer single-process mode.
  if (RenderProcessHost::run_renderer_in_process() &&
      options_.metrics_name_ !=
          proxy_resolver::mojom::ProxyResolverFactory::Name_) {
    CHECK(g_utility_main_thread_factory, base::NotFatalUntil::M159);
"""
UTILITY_MARKER = "Helium: only PAC resolution escapes renderer single-process mode."


def _read_sources(src_dir: str) -> dict[str, str]:
    result = {}
    for relative in (FACTORY, NETWORK, UTILITY):
        path = os.path.join(src_dir, relative)
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        with open(path, "r", encoding="utf-8") as handle:
            result[relative] = handle.read()
    return result


def _replace_once(path: str, content: str, old: str, new: str, label: str) -> str:
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{label} anchor expected once in {path}, found {count}")
    return content.replace(old, new, 1)


def patch_source_tree(src_dir: str) -> bool:
    sources = _read_sources(src_dir)
    factory = sources[FACTORY]
    network = sources[NETWORK]
    utility = sources[UTILITY]
    markers = (FACTORY_MARKER in factory, NETWORK_MARKER in network,
               UTILITY_MARKER in utility)
    if all(markers):
        return False
    if any(markers):
        raise RuntimeError("PAC resolver process patch is partially applied")

    factory = _replace_once(
        FACTORY, factory, FACTORY_INCLUDES_OLD, FACTORY_INCLUDES_NEW, "factory includes"
    )
    factory = _replace_once(
        FACTORY, factory, FACTORY_ANDROID_OLD, FACTORY_ANDROID_NEW,
        "Android resolver factory",
    )
    network = _replace_once(
        NETWORK, network, NETWORK_OLD, NETWORK_NEW, "PAC resolver selection"
    )
    utility = _replace_once(
        UTILITY, utility, UTILITY_INCLUDE_OLD, UTILITY_INCLUDE_NEW, "utility includes"
    )
    utility = _replace_once(
        UTILITY, utility, UTILITY_OLD, UTILITY_NEW, "utility process dispatch"
    )

    sources[FACTORY] = factory
    sources[NETWORK] = network
    sources[UTILITY] = utility
    for relative, content in sources.items():
        with open(os.path.join(src_dir, relative), "w", encoding="utf-8") as handle:
            handle.write(content)
    print("Patched old-android PAC resolver utility process")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_pac_resolver_process] {error}", file=sys.stderr)
        raise SystemExit(1)

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "patch_old_android_pac_resolver_process.py"
)
SPEC = importlib.util.spec_from_file_location(
    "patch_old_android_pac_resolver_process", MODULE_PATH
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


FACTORY_SOURCE = '''#include "base/no_destructor.h"
#if BUILDFLAG(IS_ANDROID)
#include "services/proxy_resolver/proxy_resolver_factory_impl.h"  // nogncheck crbug.com/40147906
#else
#include "content/public/browser/service_process_host.h"
#include "services/strings/grit/services_strings.h"
#endif

proxy_resolver::mojom::ProxyResolverFactory* GetProxyResolverFactory() {
  static base::NoDestructor<mojo::Remote<proxy_resolver::mojom::ProxyResolverFactory>> remote;
  if (!remote->is_bound()) {
#if BUILDFLAG(IS_ANDROID)
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
  }
  return remote->get();
}
'''

NETWORK_SOURCE = '''  if (!command_line.HasSwitch(switches::kWinHttpProxyResolver)) {
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
'''

UTILITY_SERVICE_SOURCE = '''#include "content/public/utility/utility_thread.h"
#if !BUILDFLAG(IS_ANDROID)
#include "chrome/common/importer/profile_import.mojom.h"
#include "chrome/utility/importer/profile_import_impl.h"
#include "services/proxy_resolver/proxy_resolver_factory_impl.h"  // nogncheck
#include "services/proxy_resolver/public/mojom/proxy_resolver.mojom.h"
#endif

#if !BUILDFLAG(IS_ANDROID)
auto RunProxyResolver(
    mojo::PendingReceiver<proxy_resolver::mojom::ProxyResolverFactory>
        receiver) {
  return std::make_unique<proxy_resolver::ProxyResolverFactoryImpl>(
      std::move(receiver));
}

auto RunProfileImporter(
    mojo::PendingReceiver<chrome::mojom::ProfileImport> receiver) {
  return std::make_unique<ProfileImportImpl>(std::move(receiver));
}

#endif

void RegisterIOThreadServices(mojo::ServiceFactory& services) {
#if !BUILDFLAG(IS_ANDROID)
  services.Add(RunProxyResolver);
#endif
}
'''

UTILITY_SOURCE = '''#include "content/browser/service_host/utility_process_host.h"

bool UtilityProcessHost::StartProcess() {
  process_->SetName(options_.name_);
  process_->SetMetricsName(options_.metrics_name_);

  if (RenderProcessHost::run_renderer_in_process()) {
    CHECK(g_utility_main_thread_factory, base::NotFatalUntil::M159);
    in_process_thread_.reset(g_utility_main_thread_factory(
        InProcessChildThreadParams(GetIOThreadTaskRunner({}),
                                   process_->GetInProcessMojoInvitation())));
    in_process_thread_->Start();
    return true;
  }
  return LaunchUtilityProcess();
}
'''


class OldAndroidPacResolverProcessPatchTest(unittest.TestCase):
    def _write_sources(self, root: Path):
        content = {
            PATCH.FACTORY: FACTORY_SOURCE,
            PATCH.NETWORK: NETWORK_SOURCE,
            PATCH.UTILITY: UTILITY_SOURCE,
            PATCH.UTILITY_SERVICE: UTILITY_SERVICE_SOURCE,
        }
        for relative, text in content.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return {relative: root / relative for relative in content}

    def test_routes_only_pac_factory_to_utility_process(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._write_sources(Path(temp))
            self.assertTrue(PATCH.patch_source_tree(temp))

            factory = paths[PATCH.FACTORY].read_text()
            self.assertIn(PATCH.FACTORY_MARKER, factory)
            self.assertNotIn("ProxyResolverFactoryImpl", factory)
            self.assertIn("ServiceProcessHost::Launch", factory)

            network = paths[PATCH.NETWORK].read_text()
            self.assertIn(PATCH.NETWORK_MARKER, network)
            self.assertIn("CreateWithSelfOwnedReceiver()", network)
            self.assertNotIn("Cannot use V8 Proxy resolver in single process mode.", network)

            utility = paths[PATCH.UTILITY].read_text()
            self.assertIn(PATCH.UTILITY_MARKER, utility)
            self.assertIn("options_.metrics_name_ !=", utility)
            self.assertIn("ProxyResolverFactory::Name_", utility)

            services = paths[PATCH.UTILITY_SERVICE].read_text()
            self.assertIn(PATCH.UTILITY_SERVICE_MARKER, services)
            self.assertIn(PATCH.UTILITY_IMPLEMENTATION_MARKER, services)
            self.assertIn("services.Add(RunProxyResolver);", services)
            self.assertEqual(1, services.count(PATCH.UTILITY_RESOLVER_INCLUDES))
            self.assertLess(
                services.index(PATCH.UTILITY_RESOLVER_INCLUDES),
                services.index("#if !BUILDFLAG(IS_ANDROID)"),
            )
            self.assertLess(
                services.index(PATCH.UTILITY_IMPLEMENTATION_MARKER),
                services.index("auto RunProfileImporter"),
            )

    def test_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._write_sources(Path(temp))
            self.assertTrue(PATCH.patch_source_tree(temp))
            patched = {key: path.read_text() for key, path in paths.items()}
            self.assertFalse(PATCH.patch_source_tree(temp))
            self.assertEqual(patched, {key: path.read_text() for key, path in paths.items()})

    def test_fails_closed_when_one_source_anchor_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._write_sources(Path(temp))
            paths[PATCH.UTILITY].write_text("unrelated source\n")
            with self.assertRaises(RuntimeError):
                PATCH.patch_source_tree(temp)
            self.assertEqual(FACTORY_SOURCE, paths[PATCH.FACTORY].read_text())
            self.assertEqual(NETWORK_SOURCE, paths[PATCH.NETWORK].read_text())

    def test_completes_previous_three_file_application(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._write_sources(Path(temp))
            root = Path(temp)
            for relative in (PATCH.FACTORY, PATCH.NETWORK, PATCH.UTILITY):
                text = paths[relative].read_text()
                marker = {
                    PATCH.FACTORY: PATCH.FACTORY_MARKER,
                    PATCH.NETWORK: PATCH.NETWORK_MARKER,
                    PATCH.UTILITY: PATCH.UTILITY_MARKER,
                }[relative]
                paths[relative].write_text(text + "\n" + marker + "\n")
            self.assertTrue(PATCH.patch_source_tree(temp))
            service_source = paths[PATCH.UTILITY_SERVICE].read_text()
            self.assertIn(PATCH.UTILITY_SERVICE_MARKER, service_source)
            self.assertIn(PATCH.UTILITY_IMPLEMENTATION_MARKER, service_source)
            self.assertFalse(PATCH.patch_source_tree(temp))

    def test_rejects_partially_applied_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._write_sources(Path(temp))
            paths[PATCH.NETWORK].write_text(
                NETWORK_SOURCE + "\n" + PATCH.NETWORK_MARKER + "\n"
            )
            with self.assertRaises(RuntimeError):
                PATCH.patch_source_tree(temp)


if __name__ == "__main__":
    unittest.main()

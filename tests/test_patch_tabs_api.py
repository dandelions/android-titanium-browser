import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "chromium_157" / "tabs_api.cc"


def apply_build_tab_list_patch(path: Path):
    text = path.read_text(encoding="utf-8")
    tabs_ns = "tabs_util" if "tabs_util::GetTabById" in text else "tabs_internal"
    if tabs_ns != "tabs_internal":
        text = text.replace("tabs_internal::GetTabById(", f"{tabs_ns}::GetTabById(")

    if "HeliumAndroidBuildTabListIncognitoModels" not in text:
        has_tabs_internal = "tabs_internal::CreateTabObjectHelper" in text
        helper_name = (
            "tabs_internal::CreateTabObjectHelper"
            if has_tabs_internal
            else "CreateTabObjectHelper"
        )
        old_build = f"""    TabListInterface* tab_list = TabListInterface::From(browser);
    if (!tab_list) {{ continue; }}
    for (int i = 0; i < tab_list->GetTabCount(); ++i) {{
      if (tab_index > -1 && i != tab_index) {{
        continue;
      }}

      ::tabs::TabInterface* tab = tab_list->GetTab(i);
      CHECK(tab);

      if (!MatchesTab(tab, url_patterns)) {{
        continue;
      }}

      result.Append({helper_name}(
                        tab->GetContents(), extension(), source_context_type(),
                        browser, i)
                        .ToValue());
    }}
  }}
  return result;"""
        old_build_noindent = old_build.replace(
            "    if (!tab_list) { continue; }\n",
            "if (!tab_list) { continue; }\n",
        )
        old_build_alt = old_build.replace("    if (!tab_list) { continue; }\n", "")
        new_build = f"""    TabListInterface* tab_list = TabListInterface::From(browser);
    if (!tab_list) {{ continue; }}
#if BUILDFLAG(IS_ANDROID)
    bool has_active_otr_model = false;
    for (TabModel* model : TabModelList::models()) {{
      if (model && model->IsOffTheRecord() && model->IsActiveModel()) {{
        has_active_otr_model = true;
        break;
      }}
    }}
#endif
    for (int i = 0; i < tab_list->GetTabCount(); ++i) {{
      if (tab_index > -1 && i != tab_index) {{
        continue;
      }}

      ::tabs::TabInterface* tab = tab_list->GetTab(i);
      CHECK(tab);

#if BUILDFLAG(IS_ANDROID)
      if (has_active_otr_model && query_info_.active && *query_info_.active) {{
        continue;
      }}
#endif
      if (!MatchesTab(tab, url_patterns)) {{
        continue;
      }}

      result.Append({helper_name}(
                        tab->GetContents(), extension(), source_context_type(),
                        browser, i)
                        .ToValue());
    }}
  }}
#if BUILDFLAG(IS_ANDROID)
  // HeliumAndroidBuildTabListIncognitoModels: include OTR TabModels when
  // querying tabs on Android.
  Profile* calling_profile = Profile::FromBrowserContext(browser_context());
  for (TabModel* model : TabModelList::models()) {{
    if (!model || !model->IsOffTheRecord() || !model->GetProfile()) {{
      continue;
    }}
    if (!calling_profile->IsSameOrParent(model->GetProfile())) {{
      continue;
    }}
    if (!include_incognito_information() &&
        calling_profile != model->GetProfile()) {{
      continue;
    }}
    for (int i = 0; i < model->GetTabCount(); ++i) {{
      if (tab_index > -1 && i != tab_index) {{
        continue;
      }}
      ::tabs::TabInterface* tab = model->GetTab(i);
      if (!tab || !tab->GetContents()) {{
        continue;
      }}
      bool is_active_in_window =
          model->IsActiveModel() && i == model->GetActiveIndex();
      if (query_info_.active.has_value() &&
          *query_info_.active != is_active_in_window) {{
        continue;
      }}
      std::optional<bool> saved_active = query_info_.active;
      query_info_.active.reset();
      bool matched = MatchesTab(tab, url_patterns);
      query_info_.active = saved_active;
      if (!matched) {{
        continue;
      }}
      ExtensionTabUtil::ScrubTabBehavior scrub_tab_behavior =
          ExtensionTabUtil::GetScrubTabBehavior(
              extension(), source_context_type(), tab->GetContents());
      base::DictValue tab_val =
          ExtensionTabUtil::CreateTabObject(tab->GetContents(),
                                            scrub_tab_behavior, extension(),
                                            model, i)
              .ToValue();
      tab_val.Set(tabs_constants::kActiveKey, is_active_in_window);
      tab_val.Set(tabs_constants::kSelectedKey, is_active_in_window);
      result.Append(std::move(tab_val));
    }}
  }}
#endif
  return result;"""
        build_pattern = re.compile(
            r"[ \t]*TabListInterface\* tab_list = TabListInterface::From\(browser\);\n"
            r"(?:[ \t]*if \(!tab_list\) \{ continue; \}\n)?"
            r"[ \t]*for \(int i = 0; i < tab_list->GetTabCount\(\); \+\+i\) \{\n"
            r"[ \t]*if \(tab_index > -1 && i != tab_index\) \{\n"
            r"[ \t]*continue;\n"
            r"[ \t]*\}\n\n"
            r"[ \t]*::tabs::TabInterface\* tab = tab_list->GetTab\(i\);\n"
            r"[ \t]*CHECK\(tab\);\n\n"
            r"[ \t]*if \(!MatchesTab\(tab, url_patterns\)\) \{\n"
            r"[ \t]*continue;\n"
            r"[ \t]*\}\n\n"
            r"[ \t]*result\.Append\((?:tabs_internal::)?CreateTabObjectHelper\([\s\S]*?\.ToValue\(\)\);\n"
            r"[ \t]*\}\n"
            r"[ \t]*\}\n"
            r"[ \t]*return result;"
        )
        if old_build in text:
            text = text.replace(old_build, new_build, 1)
        elif old_build_noindent in text:
            text = text.replace(old_build_noindent, new_build, 1)
        elif old_build_alt in text:
            text = text.replace(old_build_alt, new_build, 1)
        elif build_pattern.search(text):
            text = build_pattern.sub(lambda _: new_build, text, count=1)
        else:
            raise SystemExit(f"BuildTabList pattern not found in {path}")

    if tabs_ns != "tabs_internal":
        text = text.replace("tabs_internal::GetTabById(", f"{tabs_ns}::GetTabById(")

    path.write_text(text, encoding="utf-8")


class TestPatchTabsApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)
        self.tabs_api = self.work_dir / "tabs_api.cc"
        shutil.copy(FIXTURE, self.tabs_api)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_patch_chromium_157_tabs_api(self):
        # Simulate line 3112 and simulate pre-existing tabs_internal::GetTabById
        content = self.tabs_api.read_text(encoding="utf-8")
        content = content.replace(
            "    TabListInterface* tab_list = TabListInterface::From(browser);\n"
            "    for (int i = 0; i < tab_list->GetTabCount(); ++i) {",
            "    TabListInterface* tab_list = TabListInterface::From(browser);\n"
            "if (!tab_list) { continue; }\n"
            "    for (int i = 0; i < tab_list->GetTabCount(); ++i) {"
        )
        content += "\n// Test pre-existing tabs_internal call\nvoid test() { tabs_internal::GetTabById(1); }\n"
        self.tabs_api.write_text(content, encoding="utf-8")

        apply_build_tab_list_patch(self.tabs_api)
        result = self.tabs_api.read_text(encoding="utf-8")
        self.assertIn("HeliumAndroidBuildTabListIncognitoModels", result)
        self.assertIn("CreateTabObjectHelper(", result)
        self.assertNotIn("tabs_internal::CreateTabObjectHelper(", result)
        self.assertNotIn("tabs_internal::GetTabById(", result)
        self.assertIn("tabs_util::GetTabById(1);", result)

        # Idempotence
        apply_build_tab_list_patch(self.tabs_api)
        result_after = self.tabs_api.read_text(encoding="utf-8")
        self.assertEqual(result, result_after)


if __name__ == "__main__":
    unittest.main()

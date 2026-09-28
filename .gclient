solutions = [
  {
    'name': 'src',
    'url': 'https://chromium.googlesource.com/chromium/src.git@HEAD',
    'managed': False,
    'custom_deps': {
      'src/third_party/angle/third_party/VK-GL-CTS/src': None,
    },
    'custom_vars': {
      'checkout_android_prebuilts_build_tools': True,
      'checkout_pgo_profiles': True,
      'checkout_telemetry_dependencies': False,
      'codesearch': 'Debug',
    },
  },
]
hooks = [
  {
    'name': 'fetch_filter_lists',
    'condition': 'checkout_android',
    'action': ['python3',
              '../vanadium/tools/filter_lists/filter_list_download.py',
              '--output',
              'src/helium/android_config/filter_lists/filter_lists_easylist.txt',
              '--urls',
              'https://easylist-downloads.adblockplus.org/antiadblockfilters.txt',
              'https://easylist.to/easylist/easylist.txt',
              'https://easylist.to/easylist/easyprivacy.txt']
  },
  {
    'name': 'apply_subprojects_patches',
    'condition': 'checkout_android',
    'action': ['python3',
              '../vanadium/tools/common/apply_subprojects_patches.py',
              '--base_patch_dir',
              '../vanadium/subprojects_patches',
              '--src_dir',
              'src']
  },
]
target_os = ['android']

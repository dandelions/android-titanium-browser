#!/usr/bin/env python3
import os
import sys


def patch_android_manifest(src_dir: str) -> None:
    manifest_path = os.path.join(src_dir, "chrome/android/java/AndroidManifest.xml")
    if not os.path.exists(manifest_path):
        print(f"Error: {manifest_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "android.permission.READ_MEDIA_IMAGES" in content:
        print("AndroidManifest.xml already contains READ_MEDIA_IMAGES")
        return

    anchor = '    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"/>'
    replacement = (
        '    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"/>\n'
        '    <uses-permission android:name="android.permission.READ_MEDIA_IMAGES"/>\n'
        '    <uses-permission android:name="android.permission.READ_MEDIA_VIDEO"/>\n'
        '    <uses-permission android:name="android.permission.READ_MEDIA_AUDIO"/>\n'
        '    <uses-permission android:name="android.permission.READ_MEDIA_VISUAL_USER_SELECTED"/>\n'
        '    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" tools:ignore="ScopedStorage"/>'
    )

    if anchor not in content:
        print("Error: READ_EXTERNAL_STORAGE anchor not found in AndroidManifest.xml", file=sys.stderr)
        sys.exit(1)

    content = content.replace(anchor, replacement, 1)
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched chrome/android/java/AndroidManifest.xml with media & storage permissions")


def patch_select_file_dialog(src_dir: str) -> None:
    dialog_path = os.path.join(
        src_dir, "ui/android/java/src/org/chromium/ui/base/SelectFileDialog.java"
    )
    if not os.path.exists(dialog_path):
        print(f"Error: {dialog_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(dialog_path, "r", encoding="utf-8") as f:
        content = f.read()

    changed = False

    # 1. Add mDefaultDirectory field and helper methods if not present
    if "configureInitialDirectoryAndAdvanced(" not in content:
        field_anchor = "    private String mIntentAction;\n"
        field_replacement = (
            "    private String mIntentAction;\n"
            "    private @Nullable String mDefaultDirectory;\n"
        )
        if field_anchor not in content:
            print("Error: mIntentAction anchor not found in SelectFileDialog.java", file=sys.stderr)
            sys.exit(1)
        content = content.replace(field_anchor, field_replacement, 1)

        helper_anchor = "    private static boolean preferAndroidMediaPicker() {\n"
        helper_methods = """    private static boolean hasMediaStoragePermission(WindowAndroid window) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (window.hasPermission(Manifest.permission.READ_MEDIA_IMAGES)) {
                return true;
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE
                    && window.hasPermission(Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED)) {
                return true;
            }
            return false;
        }
        return window.hasPermission(Manifest.permission.READ_EXTERNAL_STORAGE);
    }

    private static void configureInitialDirectoryAndAdvanced(
            Intent intent, @Nullable String defaultDirectory, boolean isDirectoryTree) {
        intent.putExtra("android.provider.extra.SHOW_ADVANCED", true);
        intent.putExtra("android.content.extra.SHOW_ADVANCED", true);
        Uri initialUri = null;
        if (defaultDirectory != null && !defaultDirectory.isEmpty()) {
            if (defaultDirectory.startsWith("content://")) {
                initialUri = Uri.parse(defaultDirectory);
            } else if (defaultDirectory.contains("/Download")) {
                initialUri =
                        Uri.parse(
                                "content://com.android.externalstorage.documents/document/primary%3ADownload");
            }
        }
        if (initialUri == null) {
            initialUri =
                    Uri.parse(
                            isDirectoryTree
                                    ? "content://com.android.externalstorage.documents/document/primary%3A"
                                    : "content://com.android.externalstorage.documents/document/primary%3ADownload");
        }
        intent.putExtra(DocumentsContract.EXTRA_INITIAL_URI, initialUri);
    }

"""
        if helper_anchor not in content:
            print("Error: preferAndroidMediaPicker anchor not found in SelectFileDialog.java", file=sys.stderr)
            sys.exit(1)
        content = content.replace(helper_anchor, helper_methods + helper_anchor, 1)
        changed = True

    # 2. Update preferAndroidMediaPicker() to return false so Chrome's full PhotoPicker + Browse
    #    option is used instead of the restricted system ACTION_PICK_IMAGES sheet.
    old_prefer = """    private static boolean preferAndroidMediaPicker() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && sPhotoPickerDelegate != null;
    }"""
    new_prefer = """    private static boolean preferAndroidMediaPicker() {
        return false;
    }"""
    if old_prefer in content:
        content = content.replace(old_prefer, new_prefer, 1)
        changed = True

    # 3. Store defaultDirectory in selectFile()
    old_select_init = """        mIntentAction = intentAction;
        mFileTypes = new ArrayList<>(Arrays.asList(fileTypes));"""
    new_select_init = """        mIntentAction = intentAction;
        mDefaultDirectory = defaultDirectory;
        mFileTypes = new ArrayList<>(Arrays.asList(fileTypes));"""
    if old_select_init in content and "mDefaultDirectory = defaultDirectory;" not in content:
        content = content.replace(old_select_init, new_select_init, 1)
        changed = True

    # 4. Update ACTION_{OPEN,CREATE}_DOCUMENT{_TREE} handling to use configureInitialDirectoryAndAdvanced
    old_doc_init = """            if (!TextUtils.isEmpty(defaultDirectory)) {
                intent.putExtra(DocumentsContract.EXTRA_INITIAL_URI, Uri.parse(defaultDirectory));
            }"""
    new_doc_init = """            configureInitialDirectoryAndAdvanced(
                    intent,
                    defaultDirectory,
                    Intent.ACTION_OPEN_DOCUMENT_TREE.equals(mIntentAction));"""
    if old_doc_init in content:
        content = content.replace(old_doc_init, new_doc_init, 1)
        changed = True

    # 5. Request READ_MEDIA_IMAGES / READ_MEDIA_VIDEO on Android 13+ when selecting images/videos/files
    old_perm_block = """        List<String> missingPermissions = new ArrayList<>();
        String storagePermission = Manifest.permission.READ_EXTERNAL_STORAGE;
        boolean shouldUsePhotoPicker = shouldUsePhotoPicker();
        if (shouldUsePhotoPicker) {
            // The permission scenario for accessing media has evolved a bit over the years:
            // Early on, READ_EXTERNAL_STORAGE was required to access media, but that permission was
            // later deprecated. In its place (starting with Android T) READ_MEDIA_IMAGES and
            // READ_MEDIA_VIDEO were required. These permissions are strongly discouraged and an
            // Android Media Picker was introduced as a replacement which implements most of the
            // behavior of our built-in photo picker, but without requiring any permissions.
            if (!preferAndroidMediaPicker() && !window.hasPermission(storagePermission)) {
                missingPermissions.add(storagePermission);
            }
        } else if (!DeviceInfo.isDesktop()) {
            if (((mSupportsImageCapture && shouldShowImageTypes())
                            || (mSupportsVideoCapture && shouldShowVideoTypes()))
                    && !window.hasPermission(Manifest.permission.CAMERA)) {
                missingPermissions.add(Manifest.permission.CAMERA);
            }
            if (mSupportsAudioCapture
                    && shouldShowAudioTypes()
                    && !window.hasPermission(Manifest.permission.RECORD_AUDIO)) {
                missingPermissions.add(Manifest.permission.RECORD_AUDIO);
            }
        }"""

    new_perm_block = """        List<String> missingPermissions = new ArrayList<>();
        String storagePermission = Manifest.permission.READ_EXTERNAL_STORAGE;
        boolean shouldUsePhotoPicker = shouldUsePhotoPicker();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if ((shouldUsePhotoPicker || shouldShowImageTypes())
                    && !window.hasPermission(Manifest.permission.READ_MEDIA_IMAGES)
                    && window.canRequestPermission(Manifest.permission.READ_MEDIA_IMAGES)) {
                missingPermissions.add(Manifest.permission.READ_MEDIA_IMAGES);
            }
            if ((shouldUsePhotoPicker || shouldShowVideoTypes())
                    && shouldShowVideoTypes()
                    && !window.hasPermission(Manifest.permission.READ_MEDIA_VIDEO)
                    && window.canRequestPermission(Manifest.permission.READ_MEDIA_VIDEO)) {
                missingPermissions.add(Manifest.permission.READ_MEDIA_VIDEO);
            }
        } else if ((shouldUsePhotoPicker || shouldShowImageTypes() || shouldShowVideoTypes())
                && !window.hasPermission(storagePermission)) {
            missingPermissions.add(storagePermission);
        }
        if (!shouldUsePhotoPicker && !DeviceInfo.isDesktop()) {
            if (((mSupportsImageCapture && shouldShowImageTypes())
                            || (mSupportsVideoCapture && shouldShowVideoTypes()))
                    && !window.hasPermission(Manifest.permission.CAMERA)) {
                missingPermissions.add(Manifest.permission.CAMERA);
            }
            if (mSupportsAudioCapture
                    && shouldShowAudioTypes()
                    && !window.hasPermission(Manifest.permission.RECORD_AUDIO)) {
                missingPermissions.add(Manifest.permission.RECORD_AUDIO);
            }
        }"""

    if old_perm_block in content:
        content = content.replace(old_perm_block, new_perm_block, 1)
        changed = True

    # 6. Relax the requestPermissions callback so Android 14+ partial access or denied media
    #    permission falls back gracefully to launchSelectFileIntent() instead of throwing/aborting.
    old_perm_callback = """                                // TODO(finnur): Remove once we figure out the cause of
                                // crbug.com/950024.
                                if (shouldUsePhotoPicker) {
                                    if (permissions.length != requestPermissions.length) {
                                        throw new RuntimeException(
                                                String.format(
                                                        "Permissions arrays misaligned: %d != %d",
                                                        permissions.length,
                                                        requestPermissions.length));
                                    }

                                    if (!permissions[i].equals(requestPermissions[i])) {
                                        throw new RuntimeException(
                                                String.format(
                                                        "Permissions arrays don't match: %s != %s",
                                                        permissions[i], requestPermissions[i]));
                                    }
                                }

                                if (shouldUsePhotoPicker) {
                                    if (permissions[i].equals(storagePermission)
                                            || permissions[i].equals(
                                                    Manifest.permission.READ_MEDIA_IMAGES)
                                            || permissions[i].equals(
                                                    Manifest.permission.READ_MEDIA_VIDEO)) {
                                        WindowAndroid.showError(R.string.permission_denied_error);
                                        onFileNotSelected();
                                        return;
                                    }
                                }"""

    new_perm_callback = """                                if (shouldUsePhotoPicker && i < permissions.length) {
                                    if (permissions[i].equals(storagePermission)
                                            || permissions[i].equals(
                                                    Manifest.permission.READ_MEDIA_IMAGES)
                                            || permissions[i].equals(
                                                    Manifest.permission.READ_MEDIA_VIDEO)) {
                                        if (hasMediaStoragePermission(mWindowAndroid)) {
                                            continue;
                                        }
                                        launchSelectFileIntent();
                                        return;
                                    }
                                }"""

    if old_perm_callback in content:
        content = content.replace(old_perm_callback, new_perm_callback, 1)
        changed = True

    # 7. Only launch Chrome's built-in photo picker in launchSelectFileWithCameraIntent when media
    #    permission is granted; otherwise fall through to showExternalPicker.
    old_launch_photo = """        // Use the new photo picker, if available.
        if (shouldUsePhotoPicker()
                && showPhotoPicker("""
    new_launch_photo = """        // Use the new photo picker, if available and media permission is granted.
        if (shouldUsePhotoPicker()
                && hasMediaStoragePermission(mWindowAndroid)
                && showPhotoPicker("""
    if old_launch_photo in content:
        content = content.replace(old_launch_photo, new_launch_photo, 1)
        changed = True

    # 8. Ensure showExternalPicker and showExternalPickerDeprecated expose Internal Storage and
    #    default to the Downloads directory in DocumentsUI.
    old_chooser_anchor = "        Intent chooser = new Intent(Intent.ACTION_CHOOSER);"
    new_chooser_anchor = (
        "        configureInitialDirectoryAndAdvanced(getContentIntent, mDefaultDirectory, false);\n"
        "        Intent chooser = new Intent(Intent.ACTION_CHOOSER);"
    )
    if (
        old_chooser_anchor in content
        and "configureInitialDirectoryAndAdvanced(getContentIntent, mDefaultDirectory, false);"
        not in content
    ):
        content = content.replace(old_chooser_anchor, new_chooser_anchor)
        changed = True

    if not changed:
        if "hasMediaStoragePermission(" in content:
            print("SelectFileDialog.java already patched")
            return
        print("Error: Failed to apply SelectFileDialog.java patches", file=sys.stderr)
        sys.exit(1)

    with open(dialog_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched ui/android/java/src/org/chromium/ui/base/SelectFileDialog.java")


def patch_file_enum_worker_task(src_dir: str) -> None:
    task_path = os.path.join(
        src_dir,
        "components/browser_ui/photo_picker/android/java/src/org/chromium/components/browser_ui/photo_picker/FileEnumWorkerTask.java",
    )
    if not os.path.exists(task_path):
        print(f"Error: {task_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(task_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "// Helium: enumerate all media directories including Download" in content:
        print("FileEnumWorkerTask.java already patched")
        return

    old_query_block = """        String whereClause =
                directoryColumnName
                        + " LIKE ? OR "
                        + directoryColumnName
                        + " LIKE ? OR "
                        + directoryColumnName
                        + " LIKE ? OR "
                        + directoryColumnName
                        + " LIKE ? OR "
                        + directoryColumnName
                        + " LIKE ? OR "
                        + directoryColumnName
                        + " LIKE ?";
        String additionalClause = "";
        if (mIncludeImages) {
            additionalClause =
                    MediaStore.Files.FileColumns.MEDIA_TYPE
                            + "="
                            + MediaStore.Files.FileColumns.MEDIA_TYPE_IMAGE;
        }
        if (mIncludeVideos) {
            if (mIncludeImages) additionalClause += " OR ";
            additionalClause +=
                    MediaStore.Files.FileColumns.MEDIA_TYPE
                            + "="
                            + MediaStore.Files.FileColumns.MEDIA_TYPE_VIDEO;
        }
        if (!additionalClause.isEmpty()) whereClause += " AND (" + additionalClause + ")";

        String cameraDir = getCameraDirectory();
        String picturesDir = Environment.DIRECTORY_PICTURES;
        String moviesDir = Environment.DIRECTORY_MOVIES;
        String downloadsDir = Environment.DIRECTORY_DOWNLOADS;
        // Files downloaded from the user's Google Photos library go to a Restored folder.
        String restoredDir = Environment.DIRECTORY_DCIM + "/Restored";
        // On some devices, such as Samsung and Redmi, the Screenshots folder is located under
        // DCIM/Screenshots, as opposed to DCIM/Pictures/Screenshots.
        String screenshotsDir = Environment.DIRECTORY_DCIM + "/Screenshots";

        String[] whereArgs =
                new String[] {
                    // Include:
                    cameraDir + "%",
                    picturesDir + "%",
                    moviesDir + "%",
                    downloadsDir + "%",
                    restoredDir + "%",
                    screenshotsDir + "%",
                };"""

    new_query_block = """        // Helium: enumerate all media directories including Download and custom folders.
        String additionalClause = "";
        if (mIncludeImages) {
            additionalClause =
                    MediaStore.Files.FileColumns.MEDIA_TYPE
                            + "="
                            + MediaStore.Files.FileColumns.MEDIA_TYPE_IMAGE;
        }
        if (mIncludeVideos) {
            if (mIncludeImages) additionalClause += " OR ";
            additionalClause +=
                    MediaStore.Files.FileColumns.MEDIA_TYPE
                            + "="
                            + MediaStore.Files.FileColumns.MEDIA_TYPE_VIDEO;
        }
        String whereClause = additionalClause;
        String[] whereArgs = getCameraDirectory().isEmpty() ? new String[0] : new String[0];"""

    if old_query_block in content:
        content = content.replace(old_query_block, new_query_block, 1)
    elif "private static final String WHERE_DIRECTORIES =" in content:
        where_start = content.find("    private static final String WHERE_DIRECTORIES =")
        semicolon = content.find(";", where_start)
        if where_start < 0 or semicolon < 0:
            print("Error: WHERE_DIRECTORIES terminator not found in FileEnumWorkerTask.java", file=sys.stderr)
            sys.exit(1)
        content = (
            content[:where_start]
            + "    // Helium: enumerate all media directories; media type remains the only filter.\n"
            + '    private static final String WHERE_DIRECTORIES = "1";'
            + content[semicolon + 1 :]
        )
        args_start = content.find("        int count = 6 +", where_start)
        args_end = content.find("        if (mIncludeImages)", args_start)
        if args_start >= 0 and args_end > args_start:
            content = (
                content[:args_start]
                + "        int count = (mIncludeImages ? 1 : 0) + (mIncludeVideos ? 1 : 0);\n"
                + "        int index = 0;\n"
                + "        String[] whereArgs = new String[count];\n\n"
                + content[args_end:]
            )
    else:
        print("Error: query block anchor not found in FileEnumWorkerTask.java", file=sys.stderr)
        sys.exit(1)
    with open(task_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched FileEnumWorkerTask.java to enumerate all device media directories")


def patch_file_system_access_downloads(src_dir: str) -> None:
    fsa_path = os.path.join(
        src_dir,
        "chrome/browser/file_system_access/chrome_file_system_access_permission_context.cc",
    )
    if not os.path.exists(fsa_path):
        print(f"Error: {fsa_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(fsa_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "// Helium: allow Downloads directory access on Android" in content:
        print("chrome_file_system_access_permission_context.cc already patched")
        return

    old_block = """      // Similar restrictions for the downloads directory.
      BlockPath::CreateRelative(chrome::DIR_DEFAULT_DOWNLOADS,
                                BlockType::kDontBlockChildren),
      BlockPath::CreateRelative(chrome::DIR_DEFAULT_DOWNLOADS_SAFE,
                                BlockType::kDontBlockChildren),"""

    new_block = """#if !BUILDFLAG(IS_ANDROID)
      // Helium: allow Downloads directory access on Android.
      // Similar restrictions for the downloads directory.
      BlockPath::CreateRelative(chrome::DIR_DEFAULT_DOWNLOADS,
                                BlockType::kDontBlockChildren),
      BlockPath::CreateRelative(chrome::DIR_DEFAULT_DOWNLOADS_SAFE,
                                BlockType::kDontBlockChildren),
#endif"""

    if old_block not in content:
        print(
            "Error: DIR_DEFAULT_DOWNLOADS block anchor not found in chrome_file_system_access_permission_context.cc",
            file=sys.stderr,
        )
        sys.exit(1)

    content = content.replace(old_block, new_block, 1)
    with open(fsa_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched chrome_file_system_access_permission_context.cc to allow Downloads directory on Android")


def patch_download_directory_provider(src_dir: str) -> None:
    provider_path = os.path.join(
        src_dir,
        "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/DownloadDirectoryProvider.java",
    )
    if not os.path.exists(provider_path):
        print(f"Error: {provider_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(provider_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "getCustomDownloadDirectories()" in content:
        print("DownloadDirectoryProvider.java already patched")
        return

    old_task_block = """            if (hasAddtionalDirectory) {
                recordDirectoryType(DirectoryOption.DownloadLocationDirectoryType.ADDITIONAL);
            }

            return dirs;"""

    new_task_block = """            for (File customDir : getCustomDownloadDirectories()) {
                if (customDir == null) continue;
                boolean alreadyAdded = false;
                for (DirectoryOption existing : dirs) {
                    if (existing != null
                            && existing.location != null
                            && existing.location.equals(customDir.getAbsolutePath())) {
                        alreadyAdded = true;
                        break;
                    }
                }
                if (alreadyAdded) continue;
                DirectoryOption customOption =
                        toDirectoryOption(
                                customDir,
                                DirectoryOption.DownloadLocationDirectoryType.ADDITIONAL);
                if (customOption != null) {
                    customOption.name = formatCustomDirectoryName(customDir);
                    dirs.add(customOption);
                    hasAddtionalDirectory = true;
                }
            }

            if (hasAddtionalDirectory) {
                recordDirectoryType(DirectoryOption.DownloadLocationDirectoryType.ADDITIONAL);
            }

            return dirs;"""

    old_secondary_check = """            assumeNonNull(secondaryDirs);
            if (secondaryDirs.isEmpty()) return dirs;
            boolean hasAddtionalDirectory = false;"""

    new_secondary_check = """            assumeNonNull(secondaryDirs);
            boolean hasAddtionalDirectory = false;"""

    old_sdcard_block = """        return false;
    }

    private void updateDirectories() {"""

    new_sdcard_block = """        String primaryPrivateDir = PathUtils.getDownloadsDirectory();
        if (!TextUtils.isEmpty(primaryPrivateDir) && filePath.startsWith(primaryPrivateDir)) {
            return false;
        }
        File publicDownloadsDir =
                Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
        if (publicDownloadsDir != null) {
            String publicDownloadsPath = publicDownloadsDir.getAbsolutePath();
            String parentPath = new File(filePath).getParent();
            if (TextUtils.equals(parentPath, publicDownloadsPath)) {
                return false;
            }
        }
        try {
            File extRoot = Environment.getExternalStorageDirectory();
            if (extRoot != null && filePath.startsWith(extRoot.getAbsolutePath())) {
                return true;
            }
        } catch (Exception ignored) {
        }

        return false;
    }

    public static List<File> getCustomDownloadDirectories() {
        ArrayList<File> customDirs = new ArrayList<>();
        try {
            File extRoot = Environment.getExternalStorageDirectory();
            if (extRoot == null) return customDirs;
            String[] standardNames =
                    new String[] {
                        Environment.DIRECTORY_DOWNLOADS,
                        Environment.DIRECTORY_DOCUMENTS,
                        Environment.DIRECTORY_PICTURES,
                        Environment.DIRECTORY_MOVIES,
                        Environment.DIRECTORY_MUSIC,
                        Environment.DIRECTORY_DCIM,
                    };
            for (String dirName : standardNames) {
                if (TextUtils.isEmpty(dirName)) continue;
                File dir = new File(extRoot, dirName);
                if (!dir.exists()) {
                    try {
                        dir.mkdirs();
                    } catch (SecurityException ignored) {
                    }
                }
                if (dir.exists() && dir.isDirectory()) {
                    customDirs.add(dir);
                }
            }
            File downloadsRoot = new File(extRoot, Environment.DIRECTORY_DOWNLOADS);
            File[] downloadSubDirs = downloadsRoot.listFiles();
            if (downloadSubDirs != null) {
                for (File sub : downloadSubDirs) {
                    if (sub != null
                            && sub.isDirectory()
                            && !sub.isHidden()
                            && !sub.getName().startsWith(".")) {
                        customDirs.add(sub);
                    }
                }
            }
            File[] rootSubDirs = extRoot.listFiles();
            if (rootSubDirs != null) {
                for (File sub : rootSubDirs) {
                    if (sub == null
                            || !sub.isDirectory()
                            || sub.isHidden()
                            || sub.getName().startsWith(".")) {
                        continue;
                    }
                    if ("Android".equalsIgnoreCase(sub.getName())) continue;
                    boolean alreadyIncluded = false;
                    for (File existing : customDirs) {
                        if (existing.getAbsolutePath().equals(sub.getAbsolutePath())) {
                            alreadyIncluded = true;
                            break;
                        }
                    }
                    if (!alreadyIncluded) {
                        customDirs.add(sub);
                    }
                }
            }
        } catch (Exception e) {
            Log.w(TAG, "Unable to enumerate custom download directories.", e);
        }
        return customDirs;
    }

    public static String formatCustomDirectoryName(File dir) {
        try {
            File extRoot = Environment.getExternalStorageDirectory();
            if (extRoot != null) {
                String rootPath = extRoot.getAbsolutePath();
                String dirPath = dir.getAbsolutePath();
                if (dirPath.startsWith(rootPath + File.separator)) {
                    return dirPath.substring(rootPath.length() + 1);
                }
            }
        } catch (Exception ignored) {
        }
        return dir.getName();
    }

    private void updateDirectories() {"""

    if (
        old_task_block not in content
        or old_secondary_check not in content
        or old_sdcard_block not in content
    ):
        print(
            "Error: Expected anchors not found in DownloadDirectoryProvider.java",
            file=sys.stderr,
        )
        sys.exit(1)

    content = content.replace(old_secondary_check, new_secondary_check, 1)
    content = content.replace(old_task_block, new_task_block, 1)
    content = content.replace(old_sdcard_block, new_sdcard_block, 1)

    with open(provider_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched DownloadDirectoryProvider.java with custom storage directories")


def patch_download_directory_adapter(src_dir: str) -> None:
    adapter_path = os.path.join(
        src_dir,
        "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/settings/DownloadDirectoryAdapter.java",
    )
    if not os.path.exists(adapter_path):
        print(f"Error: {adapter_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(adapter_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "// Helium: preserve custom directory name" in content:
        print("DownloadDirectoryAdapter.java already patched")
        return

    old_block = """                case DirectoryOption.DownloadLocationDirectoryType.ADDITIONAL:
                    String directoryName =
                            (numOtherAdditionalDirectories > 0)
                                    ? mContext.getString(
                                            R.string.downloads_location_sd_card_number,
                                            numOtherAdditionalDirectories + 1)
                                    : mContext.getString(R.string.downloads_location_sd_card);
                    directory.name = directoryName;
                    mAdditionalOptions.add(directory);
                    numOtherAdditionalDirectories++;
                    break;"""

    new_block = """                case DirectoryOption.DownloadLocationDirectoryType.ADDITIONAL:
                    // Helium: preserve custom directory name if already provided.
                    if (directory.name == null || directory.name.isEmpty()) {
                        String directoryName =
                                (numOtherAdditionalDirectories > 0)
                                        ? mContext.getString(
                                                R.string.downloads_location_sd_card_number,
                                                numOtherAdditionalDirectories + 1)
                                        : mContext.getString(R.string.downloads_location_sd_card);
                        directory.name = directoryName;
                        numOtherAdditionalDirectories++;
                    }
                    mAdditionalOptions.add(directory);
                    break;"""

    old_init_block = """        String defaultLocation = helper.getDownloadDefaultDirectory();
        for (int i = 0; i < getCount(); i++) {
            DirectoryOption option = (DirectoryOption) getItem(i);
            if (option == null) continue;
            if (defaultLocation.equals(option.location)) {
                selectedId = i;
                break;
            }
        }
        mSelectedPosition = selectedId;"""

    new_init_block = """        String defaultLocation = helper.getDownloadDefaultDirectory();
        for (int i = 0; i < getCount(); i++) {
            DirectoryOption option = (DirectoryOption) getItem(i);
            if (option == null) continue;
            if (defaultLocation.equals(option.location)) {
                selectedId = i;
                break;
            }
        }
        if (selectedId == NO_SELECTED_ITEM_ID
                && defaultLocation != null
                && !defaultLocation.isEmpty()) {
            java.io.File customDir = new java.io.File(defaultLocation);
            if (!customDir.exists()) {
                try {
                    customDir.mkdirs();
                } catch (SecurityException ignored) {
                }
            }
            if (customDir.exists() && customDir.isDirectory()) {
                DirectoryOption customOption =
                        new DirectoryOption(
                                DownloadDirectoryProvider.formatCustomDirectoryName(customDir),
                                customDir.getAbsolutePath(),
                                customDir.getUsableSpace(),
                                customDir.getTotalSpace(),
                                DirectoryOption.DownloadLocationDirectoryType.ADDITIONAL);
                mAdditionalOptions.add(0, customOption);
                selectedId = mCanonicalOptions.size();
            }
        }
        mSelectedPosition = selectedId;"""

    if old_block not in content or old_init_block not in content:
        print(
            "Error: Expected anchors not found in DownloadDirectoryAdapter.java",
            file=sys.stderr,
        )
        sys.exit(1)

    content = content.replace(old_block, new_block, 1)
    content = content.replace(old_init_block, new_init_block, 1)

    with open(adapter_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched DownloadDirectoryAdapter.java to support custom download directory options")


def patch_download_file_provider(src_dir: str) -> None:
    provider_path = os.path.join(
        src_dir,
        "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/DownloadFileProvider.java",
    )
    if not os.path.exists(provider_path):
        print(f"Error: {provider_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(provider_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "URI_CUSTOM_EXTERNAL_PATH" in content:
        print("DownloadFileProvider.java already patched")
        return

    old_const = '    private static final String URI_EXTERNAL_PATH = "external_volume";\n'
    new_const = (
        '    private static final String URI_EXTERNAL_PATH = "external_volume";\n'
        '    private static final String URI_CUSTOM_EXTERNAL_PATH = "custom_external";\n'
    )

    old_create_end = """        for (File file : info.directoriesPreR) {
            if (file == null) continue;
            if (filePath.startsWith(file.getAbsolutePath())) {
                return buildUri(
                        URI_EXTERNAL_PATH_LEGACY,
                        filePath.substring(file.getAbsolutePath().length() + 1));
            }
        }
        return Uri.EMPTY;"""

    new_create_end = """        for (File file : info.directoriesPreR) {
            if (file == null) continue;
            if (filePath.startsWith(file.getAbsolutePath())) {
                return buildUri(
                        URI_EXTERNAL_PATH_LEGACY,
                        filePath.substring(file.getAbsolutePath().length() + 1));
            }
        }
        File extRoot = android.os.Environment.getExternalStorageDirectory();
        if (extRoot != null) {
            String rootPath = extRoot.getAbsolutePath();
            if (filePath.startsWith(rootPath + File.separator)) {
                return buildUri(
                        URI_CUSTOM_EXTERNAL_PATH,
                        filePath.substring(rootPath.length() + 1));
            }
        }
        return Uri.EMPTY;"""

    old_parse_end = """        if (path.equals(URI_EXTERNAL_PATH_LEGACY) && !info.directoriesPreR.isEmpty()) {
            // Only supports one directory.
            return info.directoriesPreR.get(0).getAbsolutePath() + File.separator + query;
        }
        return null;"""

    new_parse_end = """        if (path.equals(URI_EXTERNAL_PATH_LEGACY) && !info.directoriesPreR.isEmpty()) {
            // Only supports one directory.
            return info.directoriesPreR.get(0).getAbsolutePath() + File.separator + query;
        }
        if (path.equals(URI_CUSTOM_EXTERNAL_PATH)) {
            File extRoot = android.os.Environment.getExternalStorageDirectory();
            if (extRoot != null) {
                return extRoot.getAbsolutePath() + File.separator + query;
            }
        }
        return null;"""

    if (
        old_const not in content
        or old_create_end not in content
        or old_parse_end not in content
    ):
        print(
            "Error: Expected anchors not found in DownloadFileProvider.java",
            file=sys.stderr,
        )
        sys.exit(1)

    content = content.replace(old_const, new_const, 1)
    content = content.replace(old_create_end, new_create_end, 1)
    content = content.replace(old_parse_end, new_parse_end, 1)

    with open(provider_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched DownloadFileProvider.java to serve files from custom external storage directories")


def patch_download_settings_location_prompt(src_dir: str) -> None:
    settings_path = os.path.join(
        src_dir,
        "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/settings/DownloadSettings.java",
    )
    if not os.path.exists(settings_path):
        print(f"Error: {settings_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(settings_path, "r", encoding="utf-8") as f:
        content = f.read()

    old_methods = (
        """    private static boolean shouldEnableLocationPromptPref(Profile profile) {
        return PdfUtils.shouldOpenPdfInline(profile.isOffTheRecord())
                && DownloadDirectoryProvider.getSecondaryStorageDownloadDirectories().isEmpty();
    }""",
        """    private static boolean shouldHideLocationPromptPref(Profile profile) {
        if (isSystemFileDialogEnabled()) {
            return false;
        }
        return PdfUtils.shouldOpenPdfInline(profile.isOffTheRecord())
                && DownloadDirectoryProvider.getSecondaryStorageDownloadDirectories().isEmpty();
    }""",
    )

    if old_methods[0] in content:
        content = content.replace(
            old_methods[0],
            """    private static boolean shouldEnableLocationPromptPref(Profile profile) {
        return false;
    }""",
            1,
        )
    elif old_methods[1] in content:
        content = content.replace(
            old_methods[1],
            """    private static boolean shouldHideLocationPromptPref(Profile profile) {
        return false;
    }""",
            1,
        )
    elif "return false;" in content and (
        "shouldEnableLocationPromptPref" in content or "shouldHideLocationPromptPref" in content
    ):
        print("DownloadSettings.java already patched")
        return
    else:
        print(
            "Error: download location prompt anchor not found in DownloadSettings.java",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(settings_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched DownloadSettings.java to always show download location prompt preference")


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <chromium_src_dir>", file=sys.stderr)
        sys.exit(1)

    src_dir = sys.argv[1]
    patch_android_manifest(src_dir)
    patch_select_file_dialog(src_dir)
    patch_file_enum_worker_task(src_dir)
    patch_file_system_access_downloads(src_dir)
    patch_download_directory_provider(src_dir)
    patch_download_directory_adapter(src_dir)
    patch_download_file_provider(src_dir)
    patch_download_settings_location_prompt(src_dir)


if __name__ == "__main__":
    main()

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

    if old_query_block not in content:
        print("Error: query block anchor not found in FileEnumWorkerTask.java", file=sys.stderr)
        sys.exit(1)

    content = content.replace(old_query_block, new_query_block, 1)
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


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <chromium_src_dir>", file=sys.stderr)
        sys.exit(1)

    src_dir = sys.argv[1]
    patch_android_manifest(src_dir)
    patch_select_file_dialog(src_dir)
    patch_file_enum_worker_task(src_dir)
    patch_file_system_access_downloads(src_dir)


if __name__ == "__main__":
    main()

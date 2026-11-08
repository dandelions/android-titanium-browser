void ToolbarActionsModel::OnExtensionInstalled(
    content::BrowserContext* browser_context,
    const extensions::Extension* extension,
    bool is_update) {
  const bool is_pinned_by_feature =
      pin_mode == extensions::ManagedToolbarPinMode::kNotSet &&
      !is_enterprise_extension && !is_installed_from_sync &&
      is_feature_enabled && is_toggle_on;

  const bool is_pinned_by_policy =
      pin_mode == extensions::ManagedToolbarPinMode::kDefaultPinned;
  if (should_add_extension) {
    if (is_pinned_by_policy || is_pinned_by_feature) {
      SetActionVisibility(extension->id(), true);
    }
  }
}

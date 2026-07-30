from PyQt6.QtGui import QAction

def setup_menu_bar(window):
    menu_bar = window.menuBar()
    
    # File Menu
    file_menu = menu_bar.addMenu("&File")
    
    import_action = QAction("&Import Links from File...", window)
    import_action.triggered.connect(window.import_links_from_file)
    file_menu.addAction(import_action)
    
    settings_action = QAction("&Settings", window)
    settings_action.triggered.connect(window.open_settings_dialog)
    file_menu.addAction(settings_action)
    
    file_menu.addSeparator()
    
    exit_action = QAction("&Exit", window)
    exit_action.triggered.connect(window.close)
    file_menu.addAction(exit_action)
    
    # Help Menu
    help_menu = menu_bar.addMenu("&Help")
    
    github_action = QAction("&GitHub Repository", window)
    github_action.triggered.connect(window.open_github_link)
    help_menu.addAction(github_action)
    
    contact_action = QAction("&Contact Us", window)
    contact_action.triggered.connect(window.open_contact_link)
    help_menu.addAction(contact_action)
    
    contributing_action = QAction("C&ontributing Guide", window)
    contributing_action.triggered.connect(window.show_contributing_dialog)
    help_menu.addAction(contributing_action)
    
    changelog_action = QAction("View &Changelog", window)
    changelog_action.triggered.connect(window.show_changelog_dialog)
    help_menu.addAction(changelog_action)
    
    help_menu.addSeparator()
    
    welcome_action = QAction("&Welcome", window)
    welcome_action.triggered.connect(window.show_warning_dialog_manual)
    help_menu.addAction(welcome_action)
    
    check_update_action = QAction("Check for &Updates...", window)
    check_update_action.triggered.connect(window.manual_update_check)
    help_menu.addAction(check_update_action)

    # About Menu
    about_menu = menu_bar.addMenu("&About")
    
    about_action = QAction("&About SilverSpoon Reforged", window)
    about_action.triggered.connect(window.show_about_dialog)
    about_menu.addAction(about_action)

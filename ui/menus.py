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
    
    # 1. Getting Started & Setup
    welcome_action = QAction("&Welcome & Setup Guide", window)
    welcome_action.triggered.connect(window.show_warning_dialog_manual)
    help_menu.addAction(welcome_action)
    
    help_menu.addSeparator()
    
    # 2. Versioning & Updates
    check_update_action = QAction("Check for &Updates...", window)
    check_update_action.triggered.connect(window.manual_update_check)
    help_menu.addAction(check_update_action)
    
    changelog_action = QAction("Release &Notes & Changelog", window)
    changelog_action.triggered.connect(window.show_changelog_dialog)
    help_menu.addAction(changelog_action)
    
    help_menu.addSeparator()
    
    # 3. Repository & Community
    github_action = QAction("&Visit GitHub Repository", window)
    github_action.triggered.connect(window.open_github_link)
    help_menu.addAction(github_action)
    
    contributing_action = QAction("How to &Contribute", window)
    contributing_action.triggered.connect(window.show_contributing_dialog)
    help_menu.addAction(contributing_action)
    
    contact_action = QAction("Report &Issue & Support", window)
    contact_action.triggered.connect(window.open_contact_link)
    help_menu.addAction(contact_action)
    
    help_menu.addSeparator()
    
    # 4. Product Info
    about_action = QAction("&About SilverSpoon Reforged", window)
    about_action.triggered.connect(window.show_about_dialog)
    help_menu.addAction(about_action)




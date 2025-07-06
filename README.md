<div align="center">
<!--
IMPORTANT: Replace this placeholder URL with a real screenshot of your app's main window.
Take a screenshot, upload it to your repository, and copy the link here.
-->
<img src="https://www.google.com/search?q=https://placehold.co/800x600/242424/FFF%3Ftext%3DWaycast\nMain+Window" width=60%>
<br><br>
<!--
IMPORTANT: Replace this placeholder URL with a screenshot of the settings panel.
-->
<img src="https://www.google.com/search?q=https://placehold.co/800x400/242424/FFF%3Ftext%3DAdvanced%2BSettings" width=55%>
<br><br>
<!--
IMPORTANT: Update these badges to point to your repository.
Replace 'YOUR_USERNAME/waycast' with your GitHub username and repository name.
-->
<img alt="license" src="https://www.google.com/search?q=https://custom-icon-badges.demolab.com/github/license/YOUR_USERNAME/waycast%3Fcolor%3D3D3838%26logo%3Dlaw%26style%3Dfor-the-badge%26logoColor%3DD3C6AA%26labelColor%3D494F5A">
<img alt="stars" src="https://www.google.com/search?q=https://custom-icon-badges.demolab.com/github/stars/YOUR_USERNAME/waycast%3Fcolor%3D3D3838%26logo%3Dstar%26style%3Dfor-the-badge%26logoColor%3DD3C6AA%26labelColor%3D494F5A">
<br>
<a href="#-features">Features</a>
·
<a href="https://www.google.com/search?q=%23-requirements">Requirements</a>
·
<a href="#-installation">Installation</a>
·
<a href="#-contributing">Contributing</a>
</div>

<div align="center">
<sub>A clean and modern GTK4/Libadwaita GUI for wf-recorder.</sub>
</div>

<br>

<h2 class="description">
<sub>
<img src="https://www.google.com/search?q=https://raw.githubusercontent.com/primer/octicons/main/icons/info-16.svg" height="25" width="25">
</sub>
About Wayrec
</h2>

Waycast is a simple yet powerful graphical user interface for the excellent wf-recorder command-line utility. It provides an intuitive way to capture your screen on Wayland compositors (like Sway, Hyprland, and GNOME) without needing to memorize terminal commands.

The goal is to offer a straightforward recording experience with easy access to common options and the flexibility to configure advanced parameters when needed.

<br>

<h2>
<sub>
<img src="https://www.google.com/search?q=https://raw.githubusercontent.com/primer/octicons/main/icons/checklist-16.svg" height="25" width="25">
</sub>
Features
</h2>

Modern Interface: A clean and adaptive UI built with Python and GTK4/Libadwaita.

Flexible Recording: Record your full screen or select a specific area/window using slurp.

Easy Controls: Quickly toggle audio, set the framerate, and start/stop recording with a single click.

Advanced Customization: Fine-tune your recordings with settings for video/audio codecs, bitrates, hardware acceleration, and other wf-recorder parameters.

Persistent Settings: Your configuration is automatically saved for the next session and can be reset to defaults at any time.

<br>

<h2>
<sub>
<img src="https://www.google.com/search?q=https://raw.githubusercontent.com/primer/octicons/main/icons/package-dependencies-16.svg" height="25" width="25">
</sub>
Requirements
</h2>

To run Waycast, you need the following dependencies installed on your system:

wf-recorder: The core command-line screen recorder.

slurp: Required for area and window selection.

python3 and python3-gobject (PyGObject bindings).

gtk4 and libadwaita.

<br>

<h2>
<sub>
<img src="https://www.google.com/search?q=https://raw.githubusercontent.com/primer/octicons/main/icons/download-16.svg" height="25" width="25">
</sub>
Installation
</h2>

<sub>
    <img src="https://cdn.simpleicons.org/flatpak/white" height="20" width="20">
</sub>
Flatpak (Recommended)

</h4>

<details><summary>Click to expand</summary>
<p>

The easiest way to install Waycast is via Flatpak, which bundles all dependencies.

Note: The application is not yet on Flathub. These are the instructions for when it becomes available.

# Install from Flathub
flatpak install flathub com.github.YOUR_USERNAME.Waycast

# Run
flatpak run com.github.YOUR_USERNAME.Waycast

</p>
</details>

<h4>
<sub>
<img src="https://cdn.simpleicons.org/archlinux/white" height="20" width="20">
</sub>
Arch Linux (AUR)
</h4>

<details><summary>Click to expand>
<p>

An AUR package is available for Arch Linux users.

Note: This is a placeholder. You or a community member would need to create this package.

Using your favourite AUR helper:

# Replace 'waycast-git' with the actual package name
yay -S waycast-git

</p>
</details>

<h4>
<sub>
<img src="https://www.google.com/search?q=https://cdn.simpleicons.org/gnome/white" height="20" width="20">
</sub>
From Source
</h4>

<details><summary>Click to expand</summary>
<p>

If you prefer to run directly from the source code, ensure you have installed all the dependencies listed in the Requirements section first.

# 1. Clone the repository
git clone [https://github.com/YOUR_USERNAME/waycast.git](https://github.com/YOUR_USERNAME/waycast.git)
cd waycast

# 2. Run the application
python3 main.py

</p>
</details>

<br>

<h2>
<sub>
<img src="https://www.google.com/search?q=https://raw.githubusercontent.com/primer/octicons/main/icons/heart-16.svg" height="25" width="25">
</sub>
Contributing
</h2>

Contributions are welcome! If you have ideas for new features, find a bug, or want to improve

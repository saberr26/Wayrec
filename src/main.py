#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, Pango
import subprocess
import os
import json
import threading
import time
from pathlib import Path
import signal
import sys
import shlex

class WFRecorderApp(Adw.Application):
    """
    Main application class for the WF-Recorder GUI.
    Manages application state, settings, and the main window.
    """
    def __init__(self):
        super().__init__(application_id='com.wfrecorder.gui', flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.recording_process = None
        self.is_recording = False
        self.settings = self.load_settings()
        self.start_time = None
        self.win = None

    def do_startup(self):
        """
        Called when the application starts.
        We use this to set the color scheme to follow the system's preference.
        """
        Adw.Application.do_startup(self)
        # Handle theme preference using the modern Adw.StyleManager
        style_manager = Adw.StyleManager.get_default()
        # Set the application's theme to follow the system's setting
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)


    def do_activate(self):
        """Activates the application and presents the main window."""
        if not self.win:
            self.win = MainWindow(application=self)
        self.win.present()
        signal.signal(signal.SIGINT, self._quit_app)

    def _quit_app(self, signum, frame):
        """Handles graceful application shutdown on SIGINT."""
        if self.is_recording:
            self.win.stop_recording()
        self.quit()

    def get_default_settings(self):
        """Returns a dictionary of the default settings."""
        return {
            'output_directory': str(Path.home() / 'Videos'),
            'framerate': '30',
            'audio_enabled': True,
            'audio_device': '',
            'codec': 'libx264',
            'pixel_format': 'yuv420p',
            'audio_codec': 'aac',
            'sample_rate': '48000',
            'custom_params': '',
            'live_css_reload': False,
            'geometry': None,
            'video_bitrate': '',
            'audio_bitrate': '',
            'container_format': 'mp4',
            'hardware_acceleration': False,
            'gpu_device': '',
            'preset': 'medium',
            'crf': '23',
            'buffer_size': '',
            'threads': '',
        }

    def load_settings(self):
        """
        Loads settings from a JSON file.
        If the file doesn't exist or is invalid, it loads default settings.
        """
        settings_file = Path.home() / '.config' / 'wf-recorder-gui' / 'settings.json'
        default_settings = self.get_default_settings()

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    default_settings.update(loaded_settings)
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error loading settings, using defaults: {e}", file=sys.stderr)

        return default_settings

    def save_settings(self):
        """Saves current settings to the JSON file."""
        settings_file = Path.home() / '.config' / 'wf-recorder-gui' / 'settings.json'
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}", file=sys.stderr)

class MainWindow(Adw.ApplicationWindow):
    """
    The main window of the application.
    Contains the primary UI for recording controls and quick settings.
    Manages the slide-in settings panel.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = self.get_application()
        self.css_watcher = None

        self.set_title("WF-Recorder GUI")
        self.set_decorated(False)
        self.set_resizable(False)
        self.add_css_class("floating-window")

        self.load_css()
        self.setup_ui()
        self.update_css_watcher()

    def load_css(self):
        """Loads the custom CSS file for styling the application."""
        css_provider = Gtk.CssProvider()
        css_path = Path(__file__).parent / "styles.css"

        if not css_path.exists():
            print("styles.css not found. Using default GTK styles.", file=sys.stderr)
            return

        try:
            with open(css_path, 'r') as f:
                css_data = f.read()
            css_provider.load_from_data(css_data.encode())
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print(f"Error loading CSS: {e}", file=sys.stderr)

    def setup_ui(self):
        """Sets up the main user interface, including the sliding settings panel."""
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root_box)

        self.header_bar = Adw.HeaderBar()
        self.header_bar.add_css_class("header-bar")
        root_box.append(self.header_bar)

        self.recording_stack = Gtk.Stack()
        self.recording_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_UP_DOWN)
        self.recording_stack.set_transition_duration(350)
        self.recording_stack.set_vexpand(True)
        root_box.append(self.recording_stack)

        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.main_stack.set_transition_duration(350)

        main_content = self.create_main_content()
        self.main_stack.add_named(main_content, "main")

        self.settings_view = AdvancedSettingsView(self)
        self.main_stack.add_named(self.settings_view, "settings")
        self.recording_stack.add_named(self.main_stack, "idle_view")

        recording_view = self.create_recording_view()
        self.recording_stack.add_named(recording_view, "recording_view")

        self.title_label = Gtk.Label(label="WF-Recorder")
        self.header_bar.set_title_widget(self.title_label)

        self.settings_button = Gtk.Button(icon_name="emblem-system-symbolic")
        self.settings_button.connect("clicked", self.show_settings)
        self.header_bar.pack_start(self.settings_button)

        self.back_button = Gtk.Button(icon_name="go-previous-symbolic")
        self.back_button.connect("clicked", self.show_main_view)
        self.header_bar.pack_start(self.back_button)

        self.main_stack.connect("notify::visible-child", self.on_stack_child_changed)
        self.on_stack_child_changed(self.main_stack, None)
        self.recording_stack.set_visible_child_name("idle_view")

    def on_stack_child_changed(self, stack, param):
        """Updates the header bar based on the visible view in the stack."""
        visible_child_name = stack.get_visible_child_name()
        if visible_child_name == "main":
            self.title_label.set_text("WF-Recorder")
            self.settings_button.set_visible(True)
            self.back_button.set_visible(False)
        elif visible_child_name == "settings":
            self.title_label.set_text("Advanced Settings")
            self.settings_button.set_visible(False)
            self.back_button.set_visible(True)

    def create_main_content(self):
        """Creates the idle view with recording controls and settings."""
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.add_css_class("main-card")
        self.setup_recording_controls(content_box)
        content_box.append(Gtk.Separator())
        self.setup_quick_settings(content_box)
        content_box.append(Gtk.Separator())
        self.setup_status(content_box)
        return content_box

    def create_recording_view(self):
        """Creates the view shown during recording."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=30)
        box.add_css_class("recording-view")
        box.set_margin_top(15)
        box.set_margin_bottom(15)
        box.set_margin_start(15)
        box.set_margin_end(15)

        recording_label = Gtk.Label(label="Recording")
        recording_label.add_css_class("recording-status-label")
        recording_label.set_halign(Gtk.Align.CENTER)
        box.append(recording_label)

        spacer1 = Gtk.Box()
        spacer1.set_vexpand(True)
        box.append(spacer1)

        self.time_label = Gtk.Label(label="00:00:00")
        self.time_label.add_css_class("time-label")
        self.time_label.set_halign(Gtk.Align.CENTER)
        box.append(self.time_label)

        spacer2 = Gtk.Box()
        spacer2.set_vexpand(True)
        box.append(spacer2)

        stop_button = Gtk.Button(label="Stop")
        stop_button.connect("clicked", self.toggle_recording)
        stop_button.add_css_class("stop-button-large")
        stop_button.set_halign(Gtk.Align.CENTER)
        box.append(stop_button)
        return box

    def update_css_watcher(self):
        """Enables or disables the CSS watcher based on settings."""
        if self.app.settings.get('live_css_reload', False):
            if not self.css_watcher:
                css_file = Gio.File.new_for_path(str(Path(__file__).parent / "styles.css"))
                self.css_watcher = css_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
                self.css_watcher.connect("changed", self.on_css_file_changed)
                print("CSS watcher enabled.")
        elif self.css_watcher:
            self.css_watcher.cancel()
            self.css_watcher = None
            print("CSS watcher disabled.")

    def on_css_file_changed(self, monitor, file, other_file, event_type):
        """Callback for when the CSS file changes."""
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            print("Reloading CSS...")
            self.load_css()

    def setup_recording_controls(self, parent):
        """Sets up the recording control buttons."""
        controls_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        title_label = Gtk.Label(label="Recording Controls")
        title_label.add_css_class("section-title")
        controls_box.append(title_label)

        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        buttons_box.set_halign(Gtk.Align.CENTER)

        self.record_button = Gtk.Button()
        record_button_content = Gtk.Box(spacing=6)
        record_button_content.append(Gtk.Image.new_from_icon_name("media-record-symbolic"))
        record_button_content.append(Gtk.Label(label="Record"))
        self.record_button.set_child(record_button_content)
        self.record_button.add_css_class("record-button")
        self.record_button.connect("clicked", self.toggle_recording)
        buttons_box.append(self.record_button)

        area_button = Gtk.Button()
        area_button_content = Gtk.Box(spacing=6)
        area_button_content.append(Gtk.Image.new_from_icon_name("view-fullscreen-symbolic"))
        area_button_content.append(Gtk.Label(label="Select Area"))
        area_button.set_child(area_button_content)
        area_button.add_css_class("area-button")
        area_button.connect("clicked", self.select_area)
        buttons_box.append(area_button)

        controls_box.append(buttons_box)
        self.area_label = Gtk.Label(label="Recording: Full Screen")
        self.area_label.set_margin_top(8)
        controls_box.append(self.area_label)
        parent.append(controls_box)

    def setup_quick_settings(self, parent):
        """Sets up the collapsible quick settings section."""
        container_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        revealer_button = Gtk.Button(label="Quick Settings")
        revealer_button.add_css_class("flat")
        container_box.append(revealer_button)

        self.quick_settings_revealer = Gtk.Revealer()
        self.quick_settings_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.quick_settings_revealer.set_transition_duration(250)
        container_box.append(self.quick_settings_revealer)

        revealer_button.connect("clicked", self.on_toggle_quick_settings)
        self.quick_settings_revealer.connect("notify::child-revealed", self.on_quick_settings_revealed)

        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=10)
        self.quick_settings_revealer.set_child(settings_box)

        audio_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        audio_label = Gtk.Label(label="Record Audio:")
        audio_label.set_hexpand(True)
        audio_label.set_halign(Gtk.Align.START)
        self.audio_switch = Gtk.Switch(active=self.app.settings['audio_enabled'])
        self.audio_switch.connect("notify::active", self.on_audio_toggled)
        audio_box.append(audio_label)
        audio_box.append(self.audio_switch)
        settings_box.append(audio_box)

        framerate_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        framerate_label = Gtk.Label(label="Framerate:")
        framerate_label.set_hexpand(True)
        framerate_label.set_halign(Gtk.Align.START)
        self.framerate_entry = Gtk.Entry(
            text=self.app.settings['framerate'],
            placeholder_text="30",
            width_chars=10
        )
        self.framerate_entry.connect("changed", self.on_framerate_changed)
        framerate_box.append(framerate_label)
        framerate_box.append(self.framerate_entry)
        settings_box.append(framerate_box)
        parent.append(container_box)

    def on_toggle_quick_settings(self, button):
        self.set_resizable(True)
        is_revealed = self.quick_settings_revealer.get_child_revealed()
        self.quick_settings_revealer.set_reveal_child(not is_revealed)

    def on_quick_settings_revealed(self, revealer, param):
        GLib.timeout_add(50, lambda: self.set_resizable(False))

    def setup_status(self, parent):
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=10)
        self.status_label = Gtk.Label(label="Ready to record")
        self.status_label.add_css_class("status-label")
        self.status_label.add_css_class("status-ready")
        status_box.append(self.status_label)
        parent.append(status_box)

    def select_area(self, button):
        """Uses slurp to select a recording area."""
        try:
            result = subprocess.run(['slurp'], capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                geometry = result.stdout.strip()
                self.app.settings['geometry'] = geometry
                self.area_label.set_text(f"Area: {geometry}")
            else:
                self.app.settings['geometry'] = None
                self.area_label.set_text("Recording: Full Screen")
        except FileNotFoundError:
            self.show_error_dialog("`slurp` not found", "Please install `slurp` to use area selection.")

    def toggle_recording(self, button):
        """Starts or stops the recording."""
        if not self.app.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def build_wf_recorder_command(self):
        """Builds the wf-recorder command with proper parameter validation."""
        cmd = ['wf-recorder']
        s = self.app.settings

        # Audio settings
        if s['audio_enabled']:
            audio_device = s.get('audio_device', '').strip()
            cmd.append('-a')
            if audio_device:
                cmd.append(audio_device)

        # Video codec
        if codec := s.get('codec', '').strip():
            cmd.extend(['-c', codec])

        # Pixel format (only for non-VAAPI codecs)
        if (pix_fmt := s.get('pixel_format', '').strip()) and 'vaapi' not in s.get('codec', ''):
            cmd.extend(['-x', pix_fmt])

        # Framerate
        if (fr := s.get('framerate', '').strip()) and fr.isdigit():
            cmd.extend(['-r', fr])

        # Geometry (area selection)
        if geometry := s.get('geometry'):
            cmd.extend(['-g', geometry])

        # Video bitrate
        if vb := s.get('video_bitrate', '').strip():
            cmd.extend(['-b', vb])

        # Hardware acceleration
        if s.get('hardware_acceleration'):
            if gpu_dev := s.get('gpu_device', '').strip():
                cmd.extend(['-d', gpu_dev])

        # Codec-specific parameters (x264/x265)
        if s.get('codec', '').startswith('libx264') or s.get('codec', '').startswith('libx265'):
            if preset := s.get('preset', '').strip():
                cmd.extend(['-p', preset])
            if crf := s.get('crf', '').strip():
                cmd.extend(['-p', f'crf={crf}'])

        # Custom parameters (added before file so they don't override it)
        if custom_params := s.get('custom_params', '').strip():
            try:
                cmd.extend(shlex.split(custom_params))
            except ValueError:
                cmd.extend(custom_params.split())

        # Output file
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        container = s.get('container_format', 'mp4').strip() or 'mp4'
        filename = f"Recording_{timestamp}.{container}"
        output_path = os.path.join(s['output_directory'], filename)
        cmd.extend(['-f', output_path])

        return cmd, output_path

    def start_recording(self):
        """Constructs the wf-recorder command and starts the recording process."""
        try:
            os.makedirs(self.app.settings['output_directory'], exist_ok=True)
            cmd, output_path = self.build_wf_recorder_command()

            print(f"Starting recording with command: {' '.join(cmd)}")

            self.app.recording_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            time.sleep(0.5)

            if self.app.recording_process.poll() is not None:
                _, stderr = self.app.recording_process.communicate()
                error_msg = f"wf-recorder failed to start.\n\nCommand:\n{' '.join(cmd)}\n\nError:\n{stderr}"
                print(error_msg, file=sys.stderr)
                self.show_error_dialog("Recording Failed", f"wf-recorder error:\n{stderr}")
                self.app.recording_process = None
                return

            print("wf-recorder started successfully!")
            self.app.is_recording = True
            self.update_ui_for_recording_start()
            threading.Thread(target=self.monitor_recording_process, daemon=True).start()

        except FileNotFoundError:
            self.show_error_dialog("wf-recorder not found", "Please install wf-recorder to use this application.")
        except Exception as e:
            print(f"Exception in start_recording: {e}", file=sys.stderr)
            self.show_error_dialog("Recording failed", str(e))

    def monitor_recording_process(self):
        """Monitors the recording process and handles unexpected termination."""
        if not self.app.recording_process: return
        stdout, stderr = self.app.recording_process.communicate()
        if self.app.is_recording:
            GLib.idle_add(self.on_recording_process_ended, stdout, stderr)

    def on_recording_process_ended(self, stdout, stderr):
        """Called when recording process ends unexpectedly."""
        print("Recording process ended unexpectedly", file=sys.stderr)
        if stdout: print(f"stdout:\n{stdout}", file=sys.stderr)
        if stderr: print(f"stderr:\n{stderr}", file=sys.stderr)

        self.app.is_recording = False
        self.app.recording_process = None
        self.update_ui_for_recording_stop()

        error_message = stderr or "Recording ended unexpectedly."
        self.show_error_dialog("Recording Error", f"wf-recorder error:\n{error_message}")

    def stop_recording(self):
        """Stops the current recording process."""
        if self.app.recording_process:
            self.app.is_recording = False
            self.app.recording_process.send_signal(signal.SIGINT)
            try:
                self.app.recording_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.app.recording_process.kill()
                print("wf-recorder did not terminate gracefully, killed.", file=sys.stderr)

            self.app.recording_process = None
            self.update_ui_for_recording_stop()

    def update_ui_for_recording_start(self):
        """Updates the UI to reflect that recording has started."""
        self.recording_stack.set_visible_child_name("recording_view")
        self.header_bar.set_visible(False)
        self.app.start_time = time.time()
        GLib.timeout_add(1000, self.update_recording_time)

    def update_ui_for_recording_stop(self):
        """Updates the UI to reflect that recording has stopped."""
        self.recording_stack.set_visible_child_name("idle_view")
        self.header_bar.set_visible(True)
        self.status_label.set_text("Recording saved")
        # Use modern, non-deprecated methods for CSS classes
        self.status_label.remove_css_class("status-recording")
        self.status_label.add_css_class("status-ready")
        GLib.timeout_add(3000, lambda: self.status_label.set_text("Ready to record") if self else None)

    def update_recording_time(self):
        """Updates the recording time display every second."""
        if self.app.is_recording and self.app.start_time:
            elapsed = int(time.time() - self.app.start_time)
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.time_label.set_text(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            return True
        return False

    def on_audio_toggled(self, switch, gparam):
        self.app.settings['audio_enabled'] = switch.get_active()
        self.app.save_settings()

    def on_framerate_changed(self, entry):
        self.app.settings['framerate'] = entry.get_text()
        self.app.save_settings()

    def show_settings(self, button):
        self.main_stack.set_visible_child_name("settings")

    def show_main_view(self, button):
        self.main_stack.set_visible_child_name("main")

    def show_error_dialog(self, heading, body):
        """Displays a simple error message dialog using the modern Adw.AlertDialog."""
        dialog = Adw.AlertDialog.new(heading, body)
        dialog.add_response("ok", "OK")
        dialog.present(self)


class AdvancedSettingsView(Gtk.Box):
    """
    A view for advanced settings, designed to be used within the main window's stack.
    """
    def __init__(self, parent_window, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self.parent_window = parent_window
        self.app = parent_window.app
        self.setting_widgets = {}
        self.setup_settings_list()

    def setup_settings_list(self):
        """Sets up the scrollable list of advanced settings."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24, margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)

        output_group = self.create_settings_group("Output")
        self.add_setting_folder_chooser(output_group, "Output Directory:", 'output_directory')
        self.add_setting_entry(output_group, "Container Format:", 'container_format', "mp4")
        box.append(output_group)

        video_group = self.create_settings_group("Video")
        self.add_setting_entry(video_group, "Video Codec:", 'codec', "libx264")
        self.add_setting_entry(video_group, "Pixel Format:", 'pixel_format', "yuv420p")
        self.add_setting_entry(video_group, "Video Bitrate:", 'video_bitrate', "e.g., 5M")
        self.add_setting_entry(video_group, "Preset (x264/x265):", 'preset', "medium")
        self.add_setting_entry(video_group, "CRF (x264/x265):", 'crf', "23")
        box.append(video_group)

        audio_group = self.create_settings_group("Audio")
        self.add_setting_entry(audio_group, "Audio Codec:", 'audio_codec', "aac")
        self.add_setting_entry(audio_group, "Audio Bitrate:", 'audio_bitrate', "e.g., 192k")
        self.add_setting_entry(audio_group, "Sample Rate:", 'sample_rate', "48000")
        self.add_setting_entry(audio_group, "Audio Device:", 'audio_device', "Empty for default")
        box.append(audio_group)

        perf_group = self.create_settings_group("Hardware & Performance")
        self.add_setting_switch(perf_group, "Hardware Acceleration:", 'hardware_acceleration')
        self.add_setting_entry(perf_group, "GPU Device:", 'gpu_device', "/dev/dri/renderD128")
        self.add_setting_entry(perf_group, "Threads:", 'threads', "e.g., 4")
        self.add_setting_entry(perf_group, "Buffer Size:", 'buffer_size', "e.g., 20M")
        box.append(perf_group)

        custom_group = self.create_settings_group("Custom")
        self.add_setting_entry(custom_group, "Custom Params:", 'custom_params', "e.g., --overwrite")
        box.append(custom_group)

        dev_group = self.create_settings_group("Developer")
        self.add_setting_switch(dev_group, "Live CSS Reload:", 'live_css_reload')
        box.append(dev_group)

        restore_button = Gtk.Button(label="Restore Defaults", halign=Gtk.Align.END)
        restore_button.add_css_class("destructive-action")
        restore_button.connect("clicked", self.on_restore_defaults_clicked)
        box.append(restore_button)

        scrolled.set_child(box)
        self.append(scrolled)

    def on_restore_defaults_clicked(self, button):
        """Shows a confirmation dialog before restoring default settings."""
        dialog = Adw.AlertDialog.new(
            "Restore Default Settings?",
            "All your saved settings will be replaced with the application defaults. This cannot be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("restore", "Restore")
        dialog.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)
        # Use the async 'choose' method, which calls the callback when done.
        dialog.choose(self.parent_window, None, self.on_restore_dialog_response)

    def on_restore_dialog_response(self, source_object, result):
        """Handles the response from the restore defaults dialog."""
        try:
            # The callback receives a GAsyncResult, which we use to get the response id.
            response_id = source_object.choose_finish(result)

            if response_id == "restore":
                print("Restoring default settings...")
                self.app.settings = self.app.get_default_settings()
                self.app.save_settings()
                self.refresh_settings_ui()
        except GLib.Error as e:
            # This can happen if the dialog is cancelled (e.g., by pressing Esc).
            # We can safely ignore it in this case.
            print(f"Dialog was cancelled: {e.message}")

    def refresh_settings_ui(self):
        """Updates all setting widgets to match the current app settings."""
        for key, value in self.app.settings.items():
            if widget := self.setting_widgets.get(key):
                if isinstance(widget, Gtk.Entry):
                    widget.set_text(str(value) if value is not None else "")
                elif isinstance(widget, Gtk.Switch):
                    widget.set_active(bool(value))
                elif isinstance(widget, Gtk.Label):
                    widget.set_text(str(value))

    def create_settings_group(self, title):
        """Creates a styled group box for settings."""
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        group.add_css_class("settings-section")
        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("section-title")
        group.append(title_label)
        return group

    def add_setting_folder_chooser(self, parent, label_text, setting_key):
        """Adds a folder chooser button to a settings group."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        label = Gtk.Label(label=label_text, xalign=0)
        box.append(label)

        button = Gtk.Button(halign=Gtk.Align.FILL)
        content_label = Gtk.Label(
            label=self.app.settings[setting_key],
            ellipsize=Pango.EllipsizeMode.MIDDLE,
            xalign=0,
            hexpand=True
        )
        button.set_child(content_label)
        button.connect("clicked", self.on_choose_folder_clicked, content_label, setting_key)
        box.append(button)
        parent.append(box)
        self.setting_widgets[setting_key] = content_label

    def on_choose_folder_clicked(self, button, label_widget, setting_key):
        """Callback for the folder chooser button."""
        # Use the modern constructor for Gtk.FileChooserNative
        dialog = Gtk.FileChooserNative(
            title="Choose Output Directory",
            transient_for=self.parent_window,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="_Select",
            cancel_label="_Cancel"
        )
        dialog.connect("response", self.on_folder_selected, label_widget, setting_key)
        dialog.show()

    def on_folder_selected(self, dialog, response, label_widget, setting_key):
        """Callback for when a folder is selected."""
        if response == Gtk.ResponseType.ACCEPT:
            if folder := dialog.get_file():
                path = folder.get_path()
                self.app.settings[setting_key] = path
                label_widget.set_text(path)
                self.app.save_settings()
        dialog.destroy()

    def add_setting_entry(self, parent, label_text, setting_key, placeholder):
        """Adds a labeled text entry to a settings group."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        label = Gtk.Label(label=label_text, hexpand=True, xalign=0)
        entry = Gtk.Entry(
            text=str(self.app.settings.get(setting_key, '')),
            placeholder_text=placeholder
        )
        entry.connect("changed", self.on_setting_changed, setting_key)
        box.append(label)
        box.append(entry)
        parent.append(box)
        self.setting_widgets[setting_key] = entry

    def add_setting_switch(self, parent, label_text, setting_key):
        """Adds a labeled switch to a settings group."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        label = Gtk.Label(label=label_text, hexpand=True, xalign=0)
        switch = Gtk.Switch(active=self.app.settings.get(setting_key, False))
        switch.connect("notify::active", self.on_setting_changed, setting_key)
        box.append(label)
        box.append(switch)
        parent.append(box)
        self.setting_widgets[setting_key] = switch

    def on_setting_changed(self, widget, *args):
        """Callback to save settings when any setting widget changes."""
        setting_key = args[-1]
        if isinstance(widget, Gtk.Entry):
            self.app.settings[setting_key] = widget.get_text()
        elif isinstance(widget, Gtk.Switch):
            self.app.settings[setting_key] = widget.get_active()

        self.app.save_settings()
        if setting_key == 'live_css_reload':
            self.parent_window.update_css_watcher()

def main():
    """The main entry point for the application."""
    # The warnings about gtk-modules and theme parsing errors are related to your
    # local GTK configuration (~/.config/gtk-4.0/) and not the app itself.
    # The MESA-INTEL warnings are from your graphics driver. Both are generally harmless.
    app = WFRecorderApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())

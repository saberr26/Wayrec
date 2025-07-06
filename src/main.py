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
    """Main application class for the WF-Recorder GUI."""
    def __init__(self):
        super().__init__(application_id='com.wfrecorder.gui', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.recording_process = None
        self.is_recording = False
        self.is_paused = False
        self.settings = self.load_settings()
        self.start_time = None
        self.win = None
        self.last_output_path = None
        self.timer_id = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        # Register application actions for notifications and shortcuts
        stop_action = Gio.SimpleAction.new("stop", None)
        stop_action.connect("activate", self.on_stop_action)
        self.add_action(stop_action)

        pause_resume_action = Gio.SimpleAction.new("pause-resume", None)
        pause_resume_action.connect("activate", self.on_pause_resume_action)
        self.add_action(pause_resume_action)

        open_folder_action = Gio.SimpleAction.new("open-folder", None)
        open_folder_action.connect("activate", self.on_open_folder_action)
        self.add_action(open_folder_action)

        open_file_action = Gio.SimpleAction.new("open-file", None)
        open_file_action.connect("activate", self.on_open_file_action)
        self.add_action(open_file_action)

    def do_command_line(self, command_line):
        """Handles command line arguments. Fixes GLib-GIO-WARNING."""
        self.activate()
        return 0

    def on_stop_action(self, action, param):
        if self.is_recording and self.win:
            GLib.idle_add(self.win.stop_recording)

    def on_pause_resume_action(self, action, param):
        if self.is_recording and self.win:
            GLib.idle_add(self.win.toggle_pause_recording)

    def on_open_folder_action(self, action, param):
        if self.last_output_path:
            folder_uri = Gio.File.new_for_path(os.path.dirname(self.last_output_path)).get_uri()
            Gtk.show_uri(self.win, folder_uri, Gdk.CURRENT_TIME)

    def on_open_file_action(self, action, param):
        if self.last_output_path:
            file_uri = Gio.File.new_for_path(self.last_output_path).get_uri()
            Gtk.show_uri(self.win, file_uri, Gdk.CURRENT_TIME)


    def do_activate(self):
        if not self.win:
            self.win = MainWindow(application=self)
        self.win.present()
        signal.signal(signal.SIGINT, self._quit_app)

    def _quit_app(self, signum, frame):
        if self.is_recording:
            self.win.stop_recording()
        self.quit()

    def get_default_settings(self):
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
            'stop_shortcut': '<Control><Shift>R'
        }

    def load_settings(self):
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
        settings_file = Path.home() / '.config' / 'wf-recorder-gui' / 'settings.json'
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}", file=sys.stderr)

    def send_notification(self, notif_id, title, body, icon='media-record-symbolic', actions=None):
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        notification.set_icon(Gio.ThemedIcon.new(icon))
        if actions:
            for label, action_name in actions.items():
                notification.add_button(label, action_name)
        super().send_notification(notif_id, notification)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = self.get_application()
        self.css_watcher = None

        self.set_title("WF-Recorder GUI")
        self.set_default_size(360, -1)
        self.set_decorated(False)
        self.set_resizable(False)
        self.add_css_class("floating-window")

        self.load_css()
        self.setup_ui()
        self.setup_shortcuts()
        self.update_css_watcher()

    def load_css(self):
        css_provider_file = Gtk.CssProvider()
        css_path = Path(__file__).parent / "styles.css"
        if css_path.exists():
            try:
                css_provider_file.load_from_path(str(css_path))
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(), css_provider_file, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            except Exception as e:
                print(f"Error loading CSS from file: {e}", file=sys.stderr)

        css_provider_prog = Gtk.CssProvider()
        programmatic_css = """
        .shortcut-display {
            background-color: alpha(@theme_fg_color, 0.08);
            border: 1px solid @borders;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 0.9em;
        }
        """
        css_provider_prog.load_from_data(programmatic_css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css_provider_prog, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


    def setup_ui(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root_box)

        self.header_bar = Adw.HeaderBar()
        root_box.append(self.header_bar)

        self.recording_stack = Gtk.Stack()
        self.recording_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_UP_DOWN)
        root_box.append(self.recording_stack)

        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

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

        self.back_button = Gtk.Button(icon_name="go-previous-symbolic", visible=False)
        self.back_button.connect("clicked", self.show_main_view)
        self.header_bar.pack_start(self.back_button)

        self.main_stack.connect("notify::visible-child", self.on_stack_child_changed)
        self.recording_stack.set_visible_child_name("idle_view")

    def setup_shortcuts(self):
        for controller in list(self.observe_controllers()):
            if isinstance(controller, Gtk.ShortcutController):
                self.remove_controller(controller)

        controller = Gtk.ShortcutController()
        shortcut_str = self.app.settings.get('stop_shortcut', '<Control><Shift>R')
        trigger = Gtk.ShortcutTrigger.parse_string(shortcut_str)
        action = Gtk.NamedAction.new("app.stop")
        shortcut = Gtk.Shortcut.new(trigger, action)
        controller.add_shortcut(shortcut)
        self.add_controller(controller)

    def on_stack_child_changed(self, stack, param):
        is_settings = stack.get_visible_child_name() == "settings"
        self.title_label.set_text("Advanced Settings" if is_settings else "WF-Recorder")
        self.settings_button.set_visible(not is_settings)
        self.back_button.set_visible(is_settings)

    def create_main_content(self):
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.add_css_class("main-card")
        self.setup_recording_controls(content_box)
        content_box.append(Gtk.Separator())
        self.setup_quick_settings(content_box)
        content_box.append(Gtk.Separator())
        self.setup_status(content_box)
        return content_box

    def create_recording_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, margin_top=15, margin_bottom=15, margin_start=15, margin_end=15)
        box.add_css_class("recording-view")

        self.recording_status_label = Gtk.Label(label="Recording...")
        self.recording_status_label.add_css_class("recording-status-label")
        box.append(self.recording_status_label)

        box.append(Gtk.Box(vexpand=True))

        self.time_label = Gtk.Label(label="00:00:00")
        self.time_label.add_css_class("time-label")
        box.append(self.time_label)

        box.append(Gtk.Box(vexpand=True))

        # Create a single button for stopping
        stop_button = Gtk.Button()
        stop_button.connect("clicked", self.toggle_recording)
        stop_button.add_css_class("stop-button-large")
        stop_button.set_halign(Gtk.Align.CENTER)

        # Create a box to hold the content inside the button
        button_content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        button_content_box.set_halign(Gtk.Align.CENTER)
        button_content_box.set_valign(Gtk.Align.CENTER)
        button_content_box.set_halign(Gtk.Align.FILL) 
        button_content_box.set_valign(Gtk.Align.CENTER)
        

        # Add the "Stop" text
        stop_label = Gtk.Label(label="Stop")
        stop_label.set_margin_start(30)
        button_content_box.append(stop_label)

        spacer = Gtk.Box()
        spacer.set_hexpand(True) # This makes the spacer fill all available horizontal space
        button_content_box.append(spacer)

        # Add the shortcut label inside the button
        self.shortcut_label_recording = Gtk.ShortcutLabel(
            accelerator=self.app.settings.get('stop_shortcut', '')
        )
        self.shortcut_label_recording.add_css_class("shortcut-display")
        button_content_box.append(self.shortcut_label_recording)

        # Set the box as the child of the button
        stop_button.set_child(button_content_box)

        box.append(stop_button)
        return box

    def update_css_watcher(self):
        if self.app.settings.get('live_css_reload', False):
            if not self.css_watcher:
                css_file = Gio.File.new_for_path(str(Path(__file__).parent / "styles.css"))
                self.css_watcher = css_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
                self.css_watcher.connect("changed", self.on_css_file_changed)
        elif self.css_watcher:
            self.css_watcher.cancel()
            self.css_watcher = None

    def on_css_file_changed(self, monitor, file, other_file, event_type):
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            print("Reloading CSS...")
            self.load_css()

    def setup_recording_controls(self, parent):
        controls_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        title_label = Gtk.Label(label="Recording Controls", xalign=0)
        title_label.add_css_class("section-title")
        controls_box.append(title_label)

        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.CENTER)

        self.record_button = Gtk.Button()
        record_button_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        record_button_content.append(Gtk.Image.new_from_icon_name("media-record-symbolic"))
        record_button_content.append(Gtk.Label(label="Record"))
        self.record_button.set_child(record_button_content)
        self.record_button.add_css_class("record-button")
        self.record_button.connect("clicked", self.toggle_recording)
        buttons_box.append(self.record_button)

        area_button = Gtk.Button()
        area_button_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        area_button_content.append(Gtk.Image.new_from_icon_name("view-fullscreen-symbolic"))
        area_button_content.append(Gtk.Label(label="Select Area"))
        area_button.set_child(area_button_content)
        area_button.add_css_class("area-button")
        area_button.connect("clicked", self.select_area)
        buttons_box.append(area_button)

        controls_box.append(buttons_box)
        self.area_label = Gtk.Label(label="Area: Full Screen", margin_top=8)
        controls_box.append(self.area_label)
        parent.append(controls_box)

    def setup_quick_settings(self, parent):
        expander = Gtk.Expander(label="Quick Settings")
        parent.append(expander)

        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, margin_top=10, margin_bottom=10, margin_start=10, margin_end=10)
        expander.set_child(settings_box)

        audio_row = Adw.ActionRow(title="Record Audio")
        self.audio_switch = Gtk.Switch(active=self.app.settings['audio_enabled'], valign=Gtk.Align.CENTER)
        self.audio_switch.connect("notify::active", self.on_audio_toggled)
        audio_row.add_suffix(self.audio_switch)
        audio_row.set_activatable_widget(self.audio_switch)
        settings_box.append(audio_row)

        framerate_row = Adw.ActionRow(title="Framerate")
        self.framerate_entry = Gtk.Entry(text=self.app.settings['framerate'], placeholder_text="30", width_chars=10, valign=Gtk.Align.CENTER)
        self.framerate_entry.connect("changed", self.on_framerate_changed)
        framerate_row.add_suffix(self.framerate_entry)
        settings_box.append(framerate_row)

    def setup_status(self, parent):
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=10)
        self.status_label = Gtk.Label(label="Ready to record")
        self.status_label.add_css_class("status-label")
        self.status_label.add_css_class("status-ready")
        status_box.append(self.status_label)
        parent.append(status_box)

    def select_area(self, button):
        try:
            result = subprocess.run(['slurp'], capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                geometry = result.stdout.strip()
                self.app.settings['geometry'] = geometry
                self.area_label.set_text(f"Area: {geometry}")
            else:
                self.app.settings['geometry'] = None
                self.area_label.set_text("Area: Full Screen")
        except FileNotFoundError:
            self.show_error_dialog("`slurp` not found", "Please install `slurp` to use area selection.")

    def toggle_recording(self, button):
        if not self.app.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def toggle_pause_recording(self):
        if not self.app.recording_process: return
        
        self.app.is_paused = not self.app.is_paused
        self.app.recording_process.send_signal(signal.SIGUSR1)
        
        if self.app.is_paused:
            self.recording_status_label.set_label("Paused")
            if self.app.timer_id:
                GLib.source_remove(self.app.timer_id)
                self.app.timer_id = None
            # Store the time when pausing starts
            self.pause_start_time = time.time()
        else:
            self.recording_status_label.set_label("Recording...")
            # Adjust start_time by the duration of the pause
            if hasattr(self, 'pause_start_time'):
                pause_duration = time.time() - self.pause_start_time
                self.app.start_time += pause_duration
                del self.pause_start_time
            # Restart the timer
            if not self.app.timer_id:
                self.app.timer_id = GLib.timeout_add_seconds(1, self.update_recording_time)

        pause_button_label = "Resume" if self.app.is_paused else "Pause"
        self.app.send_notification("rec-active", "Recording in Progress...", f"Time: {self.time_label.get_text()}",
            actions={"Stop": "app.stop", pause_button_label: "app.pause-resume"})


    def build_wf_recorder_command(self):
        cmd = ['wf-recorder']
        s = self.app.settings
        if s['audio_enabled']:
            cmd.append('--audio')
            if audio_device := s.get('audio_device', '').strip():
                cmd.extend(['--audio-device', audio_device])

        if codec := s.get('codec', '').strip(): cmd.extend(['-c', codec])
        if (pix_fmt := s.get('pixel_format', '').strip()) and 'vaapi' not in s.get('codec', ''): cmd.extend(['-x', pix_fmt])
        if (fr := s.get('framerate', '').strip()) and fr.isdigit(): cmd.extend(['-r', fr])
        if geometry := s.get('geometry'): cmd.extend(['-g', geometry])
        if vb := s.get('video_bitrate', '').strip(): cmd.extend(['-b', vb])

        if s.get('hardware_acceleration'):
            if gpu_dev := s.get('gpu_device', '').strip():
                cmd.extend(['-d', gpu_dev])
        
        if s.get('codec', '').startswith(('libx264', 'libx265')):
            if preset := s.get('preset', '').strip(): cmd.extend(['-p', f"preset={preset}"])
            if crf := s.get('crf', '').strip(): cmd.extend(['-p', f"crf={crf}"])
        
        if custom_params := s.get('custom_params', '').strip():
            cmd.extend(shlex.split(custom_params))

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        container = s.get('container_format', 'mp4').strip() or 'mp4'
        filename = f"Recording_{timestamp}.{container}"
        output_path = os.path.join(s['output_directory'], filename)
        cmd.extend(['-f', output_path])
        
        self.app.last_output_path = output_path
        return cmd, output_path

    def start_recording(self):
        try:
            os.makedirs(self.app.settings['output_directory'], exist_ok=True)
            cmd, _ = self.build_wf_recorder_command()

            print(f"Starting recording with command: {' '.join(cmd)}")
            self.app.recording_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.5)

            if self.app.recording_process.poll() is not None:
                _, stderr = self.app.recording_process.communicate()
                self.show_error_dialog("Recording Failed to Start", f"wf-recorder error:\n{stderr}")
                self.app.send_notification("rec-failed", "Recording Failed", "Could not start wf-recorder.", "dialog-error-symbolic")
                self.app.recording_process = None
                return

            self.app.is_recording = True
            self.app.is_paused = False
            self.update_ui_for_recording_start()
            threading.Thread(target=self.monitor_recording_process, daemon=True).start()
            self.app.send_notification("rec-active", "Recording Started", "Your screen is now being recorded.", actions={"Stop": "app.stop", "Pause": "app.pause-resume"})

        except FileNotFoundError:
            self.show_error_dialog("wf-recorder not found", "Please install wf-recorder to use this application.")
        except Exception as e:
            self.show_error_dialog("Recording failed", str(e))

    def monitor_recording_process(self):
        if not self.app.recording_process: return
        stdout, stderr = self.app.recording_process.communicate()
        if self.app.is_recording:
             GLib.idle_add(self.on_recording_process_ended, stdout, stderr)

    def on_recording_process_ended(self, stdout, stderr):
        print("Recording process ended unexpectedly", file=sys.stderr)
        self.app.is_recording = False
        self.app.recording_process = None
        self.update_ui_for_recording_stop(cancelled=True)
        error_message = stderr or "Recording ended unexpectedly."
        self.show_error_dialog("Recording Error", f"wf-recorder error:\n{error_message}")
        self.app.send_notification("rec-failed", "Recording Failed", error_message, "dialog-error-symbolic")

    def stop_recording(self):
        if self.app.timer_id:
            GLib.source_remove(self.app.timer_id)
            self.app.timer_id = None

        if self.app.recording_process:
            self.app.is_recording = False
            self.app.recording_process.send_signal(signal.SIGINT)
            try:
                self.app.recording_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.app.recording_process.kill()
            
            self.app.recording_process = None
            self.update_ui_for_recording_stop()
            self.app.send_notification("rec-saved", "Recording Saved", f"Saved to {os.path.basename(self.app.last_output_path)}", 'video-x-generic-symbolic',
                {"Open Folder": "app.open-folder", "Open File": "app.open-file"})

    def update_ui_for_recording_start(self):
        self.recording_stack.set_visible_child_name("recording_view")
        self.header_bar.set_visible(False)
        self.app.start_time = time.time()
        self.time_label.set_text("00:00:00")
        if not self.app.timer_id:
            self.app.timer_id = GLib.timeout_add_seconds(1, self.update_recording_time)

    def update_ui_for_recording_stop(self, cancelled=False):
        self.recording_stack.set_visible_child_name("idle_view")
        self.header_bar.set_visible(True)
        status_text = "Recording cancelled" if cancelled else "Recording saved"
        self.status_label.set_text(status_text)
        self.status_label.remove_css_class("status-recording")
        self.status_label.add_css_class("status-ready")
        GLib.timeout_add_seconds(4, lambda: self.status_label.set_text("Ready to record") if self else None)
        if cancelled:
             self.app.send_notification("rec-cancelled", "Recording Cancelled", "The recording was not saved.", "edit-delete-symbolic")


    def update_recording_time(self):
        if self.app.is_recording and not self.app.is_paused:
            elapsed = int(time.time() - self.app.start_time)
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.time_label.set_text(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        return True

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
        dialog = Adw.AlertDialog.new(heading, body)
        dialog.add_response("ok", "OK")
        dialog.present(self)


class AdvancedSettingsView(Gtk.Box):
    def __init__(self, parent_window, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.parent_window = parent_window
        self.app = parent_window.app
        self.setting_widgets = {}
        self.setup_settings_list()

    def setup_settings_list(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24, margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)
        scrolled.set_child(box)
        self.append(scrolled)

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

        shortcut_group = self.create_settings_group("Shortcuts")
        self.add_shortcut_setting(shortcut_group, "In-App Stop Shortcut:", 'stop_shortcut')
        global_shortcut_info = Gtk.Label(
            label="To stop recording from anywhere, set a global shortcut in your desktop environment's system settings to run this command:\n<tt>gapplication action com.wfrecorder.gui stop</tt>",
            use_markup=True,
            wrap=True,
            xalign=0
        )
        global_shortcut_info.add_css_class("caption")
        shortcut_group.append(global_shortcut_info)
        box.append(shortcut_group)

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

    def on_restore_defaults_clicked(self, button):
        dialog = Adw.AlertDialog(title="Restore Default Settings?")
        dialog.set_body("This will replace all settings with their defaults. This cannot be undone.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("restore", "Restore")
        dialog.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.on_restore_dialog_response)
        dialog.present(self.parent_window)

    def on_restore_dialog_response(self, dialog, response_id):
        if response_id == "restore":
            self.app.settings = self.app.get_default_settings()
            self.app.save_settings()
            self.refresh_settings_ui()
            self.parent_window.setup_shortcuts()

    def refresh_settings_ui(self):
        for key, value in self.app.settings.items():
            if widget := self.setting_widgets.get(key):
                if isinstance(widget, Gtk.Entry):
                    widget.set_text(str(value) if value is not None else "")
                elif isinstance(widget, Gtk.Switch):
                    widget.set_active(bool(value))
                elif isinstance(widget, Gtk.Label):
                    widget.set_text(str(value))
                elif isinstance(widget, Gtk.Button):
                    widget.set_label(self.app.settings.get(key, ""))


    def create_settings_group(self, title):
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        group.add_css_class("settings-section")
        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("section-title")
        group.append(title_label)
        return group

    def add_setting_folder_chooser(self, parent, label_text, setting_key):
        row = Adw.ActionRow(title=label_text)
        button = Gtk.Button(
            label=self.app.settings[setting_key],
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.FILL
        )
        if button.get_child():
            button.get_child().set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        button.connect("clicked", self.on_choose_folder_clicked, setting_key)
        row.add_suffix(button)
        parent.append(row)
        self.setting_widgets[setting_key] = button.get_child()

    def on_choose_folder_clicked(self, button, setting_key):
        dialog = Gtk.FileChooserNative(
            title="Choose Output Directory",
            transient_for=self.parent_window,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.connect("response", self.on_folder_selected, button.get_child(), setting_key)
        dialog.show()

    def on_folder_selected(self, dialog, response, label_widget, setting_key):
        if response == Gtk.ResponseType.ACCEPT:
            if folder := dialog.get_file():
                path = folder.get_path()
                self.app.settings[setting_key] = path
                label_widget.set_text(path)
                self.app.save_settings()
        dialog.destroy()

    def add_setting_entry(self, parent, label_text, setting_key, placeholder):
        row = Adw.ActionRow(title=label_text)
        entry = Gtk.Entry(
            text=str(self.app.settings.get(setting_key, '')),
            placeholder_text=placeholder,
            valign=Gtk.Align.CENTER
        )
        entry.connect("changed", self.on_setting_changed, setting_key)
        row.add_suffix(entry)
        row.set_activatable_widget(entry)
        parent.append(row)
        self.setting_widgets[setting_key] = entry

    def add_setting_switch(self, parent, label_text, setting_key):
        row = Adw.ActionRow(title=label_text)
        switch = Gtk.Switch(active=self.app.settings.get(setting_key, False), valign=Gtk.Align.CENTER)
        switch.connect("notify::active", self.on_setting_changed, setting_key)
        row.add_suffix(switch)
        row.set_activatable_widget(switch)
        parent.append(row)
        self.setting_widgets[setting_key] = switch

    def add_shortcut_setting(self, parent, label_text, setting_key):
        row = Adw.ActionRow(title=label_text)
        
        shortcut_str = self.app.settings.get(setting_key, "")
        button = Gtk.Button(label=shortcut_str, valign=Gtk.Align.CENTER)
        button.connect("clicked", self.on_shortcut_button_clicked, setting_key)

        row.add_suffix(button)
        parent.append(row)
        self.setting_widgets[setting_key] = button

    def on_shortcut_button_clicked(self, button, setting_key):
        dialog = Adw.Dialog(title="Set Shortcut", transient_for=self.parent_window)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("set", "Set")
        dialog.set_response_appearance("set", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("set")
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        dialog.set_content(content_box)
        
        label = Gtk.Label(label="Press the desired key combination.")
        content_box.append(label)

        key_capture_entry = Gtk.Entry(editable=False, placeholder_text="Press a key combination...")
        content_box.append(key_capture_entry)

        dialog.accelerator = None

        controller = Gtk.EventControllerKey.new()
        def on_key_pressed(ctrl, keyval, keycode, state):
            name = Gtk.accelerator_name_with_keycode(None, keyval, keycode, state)
            label_text = Gtk.accelerator_get_label(keyval, state)
            key_capture_entry.set_text(label_text)
            dialog.accelerator = name
            return Gdk.EVENT_STOP

        controller.connect("key-pressed", on_key_pressed)
        key_capture_entry.add_controller(controller)
        
        dialog.connect("response", self.on_shortcut_dialog_response, setting_key, button)
        dialog.present()

    def on_shortcut_dialog_response(self, dialog, response_id, setting_key, button):
        if response_id == "set":
            accelerator = dialog.accelerator
            if accelerator:
                self.app.settings[setting_key] = accelerator
                button.set_label(accelerator)
                self.app.save_settings()
                self.parent_window.setup_shortcuts()
                self.parent_window.shortcut_label_recording.set_accelerator(accelerator)


    def on_setting_changed(self, widget, *args):
        setting_key = None
        for key, w in self.setting_widgets.items():
            if w == widget or (hasattr(w, 'get_child') and w.get_child() == widget):
                setting_key = key
                break
        
        if not setting_key:
            return

        if isinstance(widget, Gtk.Entry):
            self.app.settings[setting_key] = widget.get_text()
        elif isinstance(widget, Gtk.Switch):
            self.app.settings[setting_key] = widget.get_active()

        self.app.save_settings()

        if setting_key == 'live_css_reload':
            self.parent_window.update_css_watcher()


def main():
    app = WFRecorderApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())

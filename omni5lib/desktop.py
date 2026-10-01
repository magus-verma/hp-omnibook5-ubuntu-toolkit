"""Reversible GNOME shortcuts; run in the user's desktop session."""
import json
import os
from pathlib import Path
import shlex
import shutil

from .core import RepairError

MEDIA = 'org.gnome.settings-daemon.plugins.media-keys'
CUSTOM = MEDIA+'.custom-keybinding'
SHELL = 'org.gnome.shell.keybindings'
MAPPING = [(SHELL, 'screen-brightness-down', 'F3'), (SHELL, 'screen-brightness-up', 'F4'),
           (MEDIA, 'volume-mute', 'F6'), (MEDIA, 'volume-down', 'F7'), (MEDIA, 'volume-up', 'F8'),
           (MEDIA, 'mic-mute', 'F9'), (MEDIA, 'play', 'F10'), (SHELL, 'show-screenshot-ui', 'F12')]

def locations():
    return (Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))/'omni5',
            Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))/'omni5')

def bindings(mode):
    if mode not in ('super', 'direct'): raise RepairError('Unknown shortcut mode.')
    prefix = '<Super>' if mode == 'super' else ''
    return [(schema, key, prefix+fkey) for schema, key, fkey in MAPPING]

def gio():
    try:
        from gi.repository import Gio
    except ImportError as e:
        raise RepairError('Install python3-gi and use /usr/bin/python3 (the ./omni5 launcher does this).') from e
    return Gio

def restore_values(Gio, backup):
    for x in backup['changes']:
        Gio.Settings.new(x['schema']).set_strv(x['key'], x['previous'])
    for x in backup['customs']:
        s = Gio.Settings.new_with_path(CUSTOM, x['path'])
        for key, value in x['previous'].items(): s.set_string(key, value)
    Gio.Settings.new(MEDIA).set_strv('custom-keybindings', backup['previous_custom_paths'])
    Gio.Settings.sync()

def install_shortcuts(mode):
    if 'GNOME' not in os.environ.get('XDG_CURRENT_DESKTOP', '').upper() or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        raise RepairError('Run shortcuts from your logged-in GNOME desktop session.')
    Gio = gio(); state, data = locations(); backup_file = state/'shortcuts.json'
    if backup_file.exists(): raise RepairError('Shortcuts already have a backup. Run restore-shortcuts before changing modes.')
    schema_source = Gio.SettingsSchemaSource.get_default()
    changes = []
    for schema, key, binding in bindings(mode):
        definition = schema_source.lookup(schema, True)
        if not definition or not definition.has_key(key):
            raise RepairError('This GNOME version lacks '+key+'. This layout was tested with GNOME 50.')
        s = Gio.Settings.new(schema)
        if not s.is_writable(key): raise RepairError('Desktop policy prevents changing '+key)
        changes.append({'schema': schema, 'key': key, 'previous': s.get_strv(key), 'binding': binding})
    media = Gio.Settings.new(MEDIA)
    if not media.is_writable('custom-keybindings'): raise RepairError('Custom shortcuts are locked by desktop policy.')
    if not schema_source.lookup(CUSTOM, True): raise RepairError('Custom shortcut schema missing.')
    if not shutil.which('ibus'): raise RepairError('Install ibus for the emoji picker.')
    helper = data/'toggle-overview.py'
    if helper.exists(): raise RepairError('Existing overview helper requires review: '+str(helper))
    prefix = '<Super>' if mode == 'super' else ''
    targets = [('overview', 'Window overview', '/usr/bin/python3 '+shlex.quote(str(helper)), prefix+'F1'),
               ('emoji', 'Emoji picker (copy for paste)', '/usr/bin/ibus emoji', prefix+'F2')]
    customs = []
    paths = media.get_strv('custom-keybindings')
    requested = {x[2] for x in bindings(mode)} | {x[3] for x in targets}
    for path in paths:
        current = Gio.Settings.new_with_path(CUSTOM, path).get_string('binding')
        if current in requested:
            raise RepairError('An existing custom shortcut already uses '+current+'. Resolve it before installing another binding.')
    for slug, name, command, binding in targets:
        path = '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/omni5-'+slug+'/'
        if path in paths: raise RepairError('Existing toolkit shortcut requires review: '+path)
        s = Gio.Settings.new_with_path(CUSTOM, path)
        if not all(s.is_writable(k) for k in ('name', 'command', 'binding')):
            raise RepairError('Custom shortcut settings are not writable.')
        customs.append({'path': path, 'previous': {k: s.get_string(k) for k in ('name', 'command', 'binding')},
                        'values': {'name': name, 'command': command, 'binding': binding}})
    backup = {'mode': mode, 'changes': changes, 'customs': customs,
              'previous_custom_paths': paths, 'helper': str(helper)}
    state.mkdir(parents=True, exist_ok=True); state.chmod(0o700)
    # Save first, then change settings; never capture unrelated desktop or input data.
    with backup_file.open('x') as f:
        os.chmod(backup_file, 0o600); json.dump(backup, f, indent=2); f.write('\n')
    try:
        data.mkdir(parents=True, exist_ok=True)
        source = Path(__file__).resolve().parent.parent/'helpers/toggle-overview.py'
        shutil.copyfile(source, helper); helper.chmod(0o644)
        for x in changes:
            values = list(dict.fromkeys([v for v in x['previous'] if v]+[x['binding']]))
            if not Gio.Settings.new(x['schema']).set_strv(x['key'], values): raise RepairError('Cannot set '+x['key'])
        for x in customs:
            s = Gio.Settings.new_with_path(CUSTOM, x['path'])
            for key, value in x['values'].items():
                if not s.set_string(key, value): raise RepairError('Cannot set custom '+key)
        if not media.set_strv('custom-keybindings', paths+[x['path'] for x in customs]):
            raise RepairError('Cannot enable custom shortcuts.')
        Gio.Settings.sync()
        for x in changes:
            if x['binding'] not in Gio.Settings.new(x['schema']).get_strv(x['key']):
                raise RepairError('Shortcut readback failed: '+x['key'])
    except BaseException:
        restore_values(Gio, backup); helper.unlink(missing_ok=True); backup_file.unlink(missing_ok=True)
        raise
    print('Shortcuts installed. '+('Hold Windows/Super with each F key.' if mode == 'super' else 'F keys now perform media actions.'))
    print('F1 overview; F2 emoji; F3/F4 brightness; F6 mute; F7/F8 volume; F9 mic mute; F10 play; F12 screenshot.')
    print('F5 keyboard lighting remains unsupported. Restore with ./omni5 restore-shortcuts.')

def restore_shortcuts():
    Gio = gio(); state, _ = locations(); backup_file = state/'shortcuts.json'
    if not backup_file.exists(): raise RepairError('No toolkit shortcut backup found.')
    backup = json.loads(backup_file.read_text())
    restore_values(Gio, backup)
    Path(backup['helper']).unlink(missing_ok=True)
    backup_file.unlink()
    print('Previous desktop shortcuts restored.')

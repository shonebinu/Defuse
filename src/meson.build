pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'defuse'
gnome = import('gnome')

blueprints = custom_target(
    'blueprints',
    input: files(
        'header-bar.blp',
        'shortcuts-dialog.blp',
        'window.blp',
    ),
    output: '.',
    command: [
        find_program('blueprint-compiler'),
        'batch-compile',
        '@OUTPUT@',
        '@CURRENT_SOURCE_DIR@',
        '@INPUT@',
    ],
)

gnome.compile_resources(
    'defuse',
    'defuse.gresource.xml',
    gresource_bundle: true,
    install: true,
    install_dir: pkgdatadir,
    dependencies: blueprints,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
    input: 'defuse.in',
    output: 'defuse',
    configuration: conf,
    install: true,
    install_dir: get_option('bindir'),
    install_mode: 'rwxr-xr-x',
)

defuse_sources = [
    '__init__.py',
    'main.py',
    'window.py',
    'header_bar.py',
]

install_data(defuse_sources, install_dir: moduledir)

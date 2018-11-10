from   os                             import (getcwd, mkdir)
from   os.path                        import (normpath, join, abspath,
                                              exists, dirname, isabs, basename)
from   sys                            import stdout
from   shutil                         import rmtree
from   platform                       import system
from   json                           import (dump, load)
from   math                           import ceil

from   ghdl_tools.utils               import (run_console_command,
                                              get_dirs_containing_files,
                                              save_txt, get_filepaths_recursive,
                                              gtkwave_open_wave, generate_vhdl_package,
                                              signals_to_pkg_cfg)
from   ghdl_tools.regular_expressions import re_vend_srcs
from   ghdl_tools.parse               import (parse, parse_included)




###############################################################################
# GHDL COMMAND WRAPPERS
###############################################################################

def compile_vendor(vendor_name, output_path, vendor_install_path, ghdl_install_path,
                   vhdl_standard='93c', recompile=False, verbose=False):
    """ Compile vendor libraries

    For a list of supported libraries check your GHDL version.
    This should be run once in the system, the compiled result can be reused by
    pointing to the compiled output directory.
    """

    if vhdl_standard in ('93', '93c', 93):
        vhdl_standard = 'VHDL93'
    elif vhdl_standard in ('2008', '08', 2008, 8):
        vhdl_standard = 'VHDL2008'
    else:
        raise ValueError('Invalid VHDL standard. Valid values are 93, 2008')


    output_path_norm = abspath(output_path)
    if (not recompile) and get_dirs_containing_files(output_path_norm, extension='.cf'):
        message = vendor_name + ' libraries found, not recompiling'
        if verbose:
            stdout.write(message + '\n')
        return 2, message
    else:
        if verbose:
            stdout.write('Compiling ' + vendor_name + ' libraries...\n')

    with open(join(ghdl_install_path, 'lib/vendors/config.sh'), 'r', encoding='utf-8') as settings_file:
        srcs_dir = {re_vend_srcs.search(line).group('name').lower(): re_vend_srcs.search(line).group('path')
                    for line in settings_file.readlines() if re_vend_srcs.search(line)}
    vendor_sources_dir = join(normpath(vendor_install_path), normpath(srcs_dir[vendor_name.lower().replace('-','')]))


    OS = system()
    compile_vendor_command = \
        normpath( join( join(ghdl_install_path, 'lib/vendors'),
                        ('compile-' + vendor_name + ('.ps1' if OS == 'Windows' else '.sh')) ) ) + \
        ' -Source "' + vendor_sources_dir + '"' + \
        ' -' + vhdl_standard + \
        ' -SuppressWarnings' + \
        ' -Output "' + output_path_norm + '"' + \
        ' -All -GHDL "' + normpath( join(ghdl_install_path, 'bin') ) + '"'
    if OS == 'Windows':
        compile_vendor_command = 'powershell.exe -Command "' + compile_vendor_command + '"'

    if OS not in ('Windows', 'Linux','Darwin'):
        raise ValueError('Automatic vendor libs compilation is only available in Linux, Mac and Windows')

    return run_console_command(compile_vendor_command)



def import_file(file_path, workdir, vhdl_standard='93c'):
    """ Import and get the entity and architectures present in the file
    """

    file_path = normpath(file_path)
    workdir = normpath(workdir)
    import_command = \
        'ghdl -i -v --ieee=synopsys -fexplicit' + \
        ((' --std=' + str(vhdl_standard)) if vhdl_standard else '') + \
        ' --workdir="' + workdir + '"' + \
        ' "' + file_path + '"'
    command_run_result = run_console_command(import_command)
    error = command_run_result[0]
    terminal_output = command_run_result[1]
    units_description = parse_included(terminal_output)
    return error, terminal_output, import_command, units_description



def make_entity(entity_name, workdir, additional_libs, vhdl_standard='93c'):
    """ Compile the imported files

    Requires previous import_file.
    """

    workdir = normpath(workdir)
    additional_libs = ' -P' + ' -P'.join(additional_libs) if additional_libs else ''
    make_command = \
        'ghdl -m -v --ieee=synopsys -fexplicit' + \
        ((' --std=' + str(vhdl_standard)) if vhdl_standard else '') + \
        ' --workdir="' + workdir + '"' + \
        additional_libs + \
        ' ' + entity_name
    return run_console_command(make_command) + (make_command,)



def dump_xml_file(file_path, workdir, additional_libs, output_file_path):
    """ Generate a (large) XML representation of the VHDL code
    """

    additional_libs = ' -P ' + ' -P '.join(additional_libs) if additional_libs else ''
    output_file_path = abspath(output_file_path)
    dump_xml_command = \
        'ghdl --file-to-xml -v --ieee=synopsys -fexplicit' + \
        ' --workdir="' + workdir + '"' + \
        ' "' + file_path + '"'
    error, xml = run_console_command(dump_xml_command)
    if not error:
        save_txt(xml, output_file_path)
    return error, output_file_path



def generate_cross_references_html(file_path, workdir, additional_libs, output_path=''):
    """ Generate a navigable HTML tree of the provided files

    Requires previous make_entity.
    """

    additional_libs = ' -P ' + ' -P '.join(additional_libs) if additional_libs else ''
    if output_path:
        output_path = abspath(output_path)
        if not exists(output_path):
            mkdir(output_path)

    gen_cross_refs_command = \
        'ghdl --xref-html -v --ieee=synopsys -fexplicit' + \
        ' --workdir="' + workdir + '"' + \
        ' --format=css' + \
        (' -o ' + ('"' + output_path + '"') if output_path else '') + \
        ' "' + file_path + '"'
    return run_console_command(gen_cross_refs_command)



def analyze_file(file_path, workdir, additional_libs):
    """ Analyze source file (-a)
    """

    additional_libs = ' -P ' + ' -P '.join(additional_libs) if additional_libs else ''
    analyze_command = \
        'ghdl -a -v --ieee=synopsys -fexplicit' + \
        ' --workdir="' + workdir + '"' + \
        additional_libs + \
        ' "' + file_path + '"'
    return run_console_command(analyze_command)



def elaborate_entity(entity_name, workdir):
    """ Elaborate source file (-e)
    """

    elaborate_command = \
        'ghdl -e -v --ieee=synopsys -fexplicit' + \
        ' --workdir="' + workdir + '"' + \
        ' ' + entity_name
    return run_console_command(elaborate_command)



def run_tb(testbench_name, workdir, run_time='1us'):
    """ Run the desired testbench (-r)

    Provide the entity name in the testbench, not the file name.
    Requires previous (-a, -e) or (-i, -m).
    """

    workdir = normpath(workdir)
    run_command = \
        'ghdl -r -v --ieee=synopsys -fexplicit' + \
        ' --workdir="' + workdir + '" ' + \
        testbench_name + \
        ' --wave="' + join(workdir, (testbench_name + '.ghw')) + '"' + \
        (' --stop-time=' + run_time if (run_time and not run_time == '0') else ' --no-run --disp-tree=inst')
    return run_console_command(run_command)



class SetExt(set):
    """ Extend the class set
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def append(self, data):
        self.update(data)



###############################################################################
# GHDL
###############################################################################

class GHDL():
    """ GHDL abstraction

        Contains the methods, configuration and paths needed to run GHDL and
        the tools provided by this package. When automating a simulation, using
        these class methods produce the same results but require even fewer
        arguments than using the standalone functions because references and
        results are stored and reused.
    """

    def __init__(self, verbose=False, install_path=None, vhdl_standard=None,
                 work_dir_path=None, compiled_libs_paths=None, always_reimport=True,
                 sources_directories=None, sources_paths=None, exclude_files=None,
                 testbench=None, waves_dir=None):
        self.verbose = verbose
        self.vhdl_standard = vhdl_standard or '93c'
        self.work_dir_path = normpath(work_dir_path) if work_dir_path else join(getcwd(), normpath('./work/'))

        if compiled_libs_paths:
            self.compiled_libs_paths = SetExt()
            self.add_compiled_libs(compiled_libs_paths)
        else:
            self.compiled_libs_paths = SetExt([abspath('./compiled')])

        self.load_config_from_file()
        if install_path:
            self.install_path = install_path
        else:
            for try_path in ('C:/GHDL', 'C:/Programs/GHDL', 'D:/GHDL', 'D:/Programs/GHDL',
                             'C:/Progra~1/GHDL', 'C:/Progra~2/GHDL'):
                if exists(try_path):
                    self.install_path = try_path
                    break

        self.always_reimport = always_reimport
        self.exclude_files = exclude_files or []
        self.sources_paths = SetExt(sources_paths) if sources_paths else SetExt()
        self._sources_directories = set()
        self.sources_directories = sources_directories or [getcwd()]
        self.testbench = testbench if isinstance(testbench, list) else ([testbench] if testbench else [])
        self.waves_dir = normpath(waves_dir) if waves_dir else None



    def __repr__(self):
        return 'GHDL configuration (VHDL ' + str(self.vhdl_standard) + ')'



    def __str__(self):
        return 'GHDL configuration (VHDL ' + str(self.vhdl_standard) + ')'



    @property
    def install_path(self):
        if not self.config['install_path']:
            self.load_config_from_file()
        return self.config['install_path']

    @install_path.setter
    def install_path(self, val):
        self.config['install_path'] = val
        self.save_config_to_file()



    @property
    def sources_directories(self):
        return self._sources_directories

    @sources_directories.setter
    def sources_directories(self, val):
        self._sources_directories = self._sources_directories.update(val) if self._sources_directories else set(val)
        self.add_sources_from_dir(val, exclude_files=self.exclude_files)



    def load_config_from_file(self):
        """ Load persistent configuration

        For example, the GHDL install path, so that it only has to be input
        once per project.
        """

        try:
            with open(join(self.work_dir_path, 'config')) as infile:
                self.config = load(infile)
        except FileNotFoundError:
            self.config = {
                'install_path': '',
                'imported_entities': {},
                'imported_packages': {},
            }
            self.save_config_to_file()



    def save_config_to_file(self):
        """ Save persistent configuration

        For example, the GHDL install path, so that it only has to be input
        once per project.
        """

        try:
            with open(join(self.work_dir_path, 'config'), 'w') as outfile:
                dump(self.config, outfile)
        except FileNotFoundError:
            mkdir(self.work_dir_path)
            with open(join(self.work_dir_path, 'config'), 'w') as outfile:
                dump(self.config, outfile)



    def signals_to_package(self, signals, name):
        self.generate_vhdl_package(signals_to_pkg_cfg(signals), name)



    def generate_vhdl_package(self, pkg_cfg, package_name):
        generate_vhdl_package(pkg_cfg, package_name, self.work_dir_path)



    def add_compiled_libs(self, directory_paths):
        """ Find the paths that contain compiled libs and add them to compiled_libs_paths
        """

        if not isinstance(directory_paths, list):
            directory_paths = [directory_paths]
        for directory_path in directory_paths:
            self.compiled_libs_paths.update([abspath(directory) for directory in get_dirs_containing_files(directory_path, extension='.cf')])



    def compile_vendor(self, vendor_name, vendor_install_path, output_path='./compiled/vendor', recompile=False):
        """ compile_vendor wrapper
        """

        output_path = join(normpath(output_path), vendor_name)
        if not self.install_path:
            raise ValueError('compile_vendor requires GHDL install_path')

        command_run_result = compile_vendor(
            vendor_name,
            output_path,
            vendor_install_path,
            self.install_path,
            self.vhdl_standard,
            recompile,
            self.verbose
        )
        if command_run_result[0] == 0 and self.verbose:
            stdout.write('Finished compilation of ' + vendor_name + '\n')

        self.add_compiled_libs(output_path)
        return command_run_result



    def add_sources_from_dir(self, sources_directories, extensions=['.vhd', '.vhdl'],
                             include_files=[], exclude_files=[]):
        """ Scan a directory for sources

        Args:
            sources_directories: Specify which paths to scan
            extensions: File extensions that should be included
            include_files: File name list, if provided only these files will be
                used. The path is automatically found.
            exclude_files: File names in this list will not be used.
        """

        vhd_paths = set()
        for src_folder in sources_directories:
            vhd_paths.update( get_filepaths_recursive(src_folder, extensions, include_files, exclude_files) )
        if self.verbose:
            stdout.write('Found ' + str(len(vhd_paths)) + ' VHDL files\n')
        self.sources_paths.update(vhd_paths)



    def import_file(self, file_path):
        """ Import file and save the results
        """

        error, terminal_output, import_command, units_description = import_file(file_path, self.work_dir_path, self.vhdl_standard)
        if not error:
            for unit_description in units_description:
                if unit_description[0] == 'entity':
                    self.config['imported_entities'][unit_description[1]] = file_path
                    self.save_config_to_file()
                elif unit_description[0] == 'package':
                    self.config['imported_packages'][unit_description[1]] = file_path
                    self.save_config_to_file()
        return error, terminal_output, import_command, units_description



    def make_entity(self, entity):
        """ make_entity wrapper
        """

        return make_entity(entity, self.work_dir_path, self.compiled_libs_paths, self.vhdl_standard)



    def dump_xml_file(self, file_path, output_file_path):
        """ dump_xml_file wrapper
        """

        return dump_xml_file(file_path, self.work_dir_path, self.compiled_libs_paths, output_file_path)



    def generate_cross_references_html(self, file_path, output_path=''):
        """ generate_cross_references_html wrapper
        """

        return generate_cross_references_html(file_path, self.work_dir_path, self.compiled_libs_paths, output_path)



    def run_tb(self, entity, run_time):
        """ run_tb wrapper
        """

        return run_tb(entity, self.work_dir_path, run_time)



    def parse_entity(self, entity):
        """ Parse an entity architecture
        """

        error, terminal_output = run_tb(entity, self.work_dir_path, 0)
        return parse(terminal_output)



    def open_waves(self, entity):
        """ Open the wave files of all the simulation runs using GTKWave

        If gtkw files are found, they are used to configure the waveform display.
        """

        self.load_config_from_file()

        entity_dir = dirname(self.config['imported_entities'][entity.lower()])
        if self.waves_dir:
            if isabs(normpath(self.waves_dir)):
                testbench_waves_dir = normpath(self.waves_dir)
            else:
                testbench_waves_dir = join(entity_dir, normpath(self.waves_dir))
        else:
            testbench_waves_dir = join(entity_dir, normpath('./waves/'))

        found_wave_files = get_filepaths_recursive(testbench_waves_dir, extensions=['.gtkw'])

        ghw_path = join(self.work_dir_path, (entity + '.ghw'))
        if found_wave_files:
            if self.verbose:
                stdout.write( ' ' * 2 + 'Found ' + str(len(found_wave_files)) +
                              ' wave file' + ('s' if len(found_wave_files) > 1 else '') + '\n')
            for gtkw_file in found_wave_files:
                gtkwave_open_wave(ghw_path, gtkw_file)
                if self.verbose:
                    stdout.write(' ' * 4 + 'Opening ' + basename(gtkw_file) + '\n')
        else:
            gtkwave_open_wave(ghw_path)



    def import_sources(self):
        """ Automate the import process

        The desired paths and other configurations must be set before running
        this procedure.
        """

        has_to_import = True
        if exists(self.work_dir_path):
            if not self.always_reimport and get_dirs_containing_files(self.work_dir_path, extension='.cf'):
                has_to_import = False
                if self.verbose:
                    stdout.write('Not reimporting sources\n')
                return
            else:
                # Cleanup work dir
                rmtree(self.work_dir_path)
                mkdir(self.work_dir_path)
        else:
            mkdir(self.work_dir_path)

        if self.verbose:
            stdout.write('Importing included sources...\n')
        imported = 0
        previous_len = 0
        for file_path in self.sources_paths:
            import_error, terminal_output, import_command, units_description = self.import_file(file_path)

            if import_error:
                stdout.write('\nERROR Importing ' + file_path + '\n' + terminal_output + '\n' +
                             'For more details, you can run:\n' + import_command + '\n')
            else:
                if self.verbose:
                    # Progress bar
                    imported += 1
                    i = ceil(imported * 20 / len(self.sources_paths))
                    stdout.write('\r')
                    stdout.write(' ' * 2 + '[%-20s] %d%% ' % ('='*i, imported / len(self.sources_paths) * 100))
                    imported_message = 'Imported ' + ' '.join([unit[1] for unit in units_description])
                    stdout.write(imported_message)
                    current_len = len(imported_message)
                    stdout.write(' ' * ((previous_len - current_len) if previous_len > current_len else 0))
                    previous_len = current_len
            if self.verbose:
                stdout.flush()
        if self.verbose:
            stdout.write('\n')



    def parse(self, show_output=False):
        """ Parse all the testbenches
        """

        result = []
        for entity in self.testbench:
            result.append(self.parse_entity(entity))
            if show_output:
                stdout.write('* ' + entity.upper() + ' TREE:\n')
                result[-1].print_children()
            stdout.write('\n')

        return result




    def run(self, run_time=None, open_waves=True):
        """ Makes, runs and opens the waveforms for the configured testbenches

        Requires previous import self.import_sources or equivalent.
        """

        run_time = run_time or '1us'

        if self.verbose:
            if self.testbench:
                stdout.write(
                    ' '.join([
                        'Running testbench' + ('es' if (len(self.testbench) > 1) else ''),
                        ' '.join([entity for entity in self.testbench]),
                        '\n'
                    ])
                )
            else:
                stdout.write('No testbench selected\n')


        # Import
        if self.testbench:
            self.import_sources()

        # Make
        for entity in self.testbench:
            if self.verbose:
                stdout.write('Make ' + entity + '\n')
            make_error, make_terminal_output, make_command = self.make_entity(entity)

            # Run
            if not make_error:
                if self.verbose:
                    stdout.write('Running testbench ' + entity + ' ' + (run_time or '') + '...\n')

                error_occurred, run_terminal_output = self.run_tb(entity, run_time)

                if error_occurred:
                    stdout.write('ERROR Running testbench ' + entity + '\n')
                    stdout.write(run_terminal_output + '\n')
                elif 'report' in run_terminal_output:
                    stdout.write('Output of testbench run ' + entity + '\n')
                    stdout.write(run_terminal_output + '\n')

                # Open wave files
                if not error_occurred and open_waves:
                    if self.verbose:
                        stdout.write('Opening ' + entity + ' wave files\n')
                    self.open_waves(entity)

            else:
                stdout.write('ERROR Make ' + entity + '\n')
                if make_terminal_output:
                    stdout.write(make_terminal_output + '\n')
                stdout.write('For more details, you can run:' + '\n' + make_command + '\n')

import os
from subprocess import check_output, Popen, DEVNULL, STDOUT, check_call, CalledProcessError




###############################################################################
# GENERIC HELPER FUNCTIONS
###############################################################################

def save_txt(text, path):
    with open(path, "w+") as f:
        f.write(''.join(text.split('\n')))



def getBit(y, x):
    return str((x>>y)&1)



def int_tobin(x, count=8):
    shift = range(count-1, -1, -1)
    bits = map(lambda y: getBit(y, x), shift)
    return "".join(bits)



def create_vhdl_package(data_dict, package_name, file_path, indentation=2):
    """Generate a VHDL package with the provided constants.
    
    Data can be provided as integer or as a binary representation string.
    Width will be extended according to the type.

    Args:
        data_dict (dict): A dictionary containing all the signals to be
            included in the package with the following format:

            data_dict = {
                'constant_0': {
                    'data': [1, '0'],
                    'type': 'std_logic',
                    'width': None,
                },
                'constant_1': {
                    'data': 8,
                    'type': 'integer',
                    'width': None,
                },
                'constant_2': {
                    'data': [244, 1, -1, '11100', '0101'],
                    'type': 'signed',
                    'width': 9,
                },
                'constant_3': {
                    'data': ['1001', 1, 32],
                    'type': 'unsigned',
                    'width': 17,
                },
                'constant_4': {
                    'data': [24, 8932, '10101110110110', 142],
                    'type': 'std_logic_vector',
                    'width': 14,
                },
            }

        package_name (str): Package name.
        file_path (str): Output file path.
    Returns:
        bool: The return value. True for error, False otherwise.
    """

    package_text = []
    package_text.append('')
    
    package_text.append('library   ieee;')
    package_text.append('use       ieee.std_logic_1164.all;')
    package_text.append('use       ieee.numeric_std.all;')
    package_text.append('')

    package_text.append('package ' + package_name + ' is')
    package_text.append('')


    for constant_name in data_dict.keys():
        data_w = data_dict[constant_name]['width']
        data_type = data_dict[constant_name]['type']

        package_text.append(' ' * 1 * indentation)

        if isinstance(data_dict[constant_name]['data'], list):
            is_array = True
        else:
            is_array = False
            data_dict[constant_name]['data'] = [data_dict[constant_name]['data']]
        array_len = len(data_dict[constant_name]['data'])


        if is_array:
            package_text[-1] += 'type T_' + constant_name.upper() + ' is array(0 to '
            package_text[-1] += str(array_len) + ' - 1) of '

            if data_type in ('std_logic', 'integer'):
                package_text[-1] += data_type + ';'
            else:
                package_text[-1] += data_type + '(' + str(data_w)
                package_text[-1] += ' - 1 downto 0);'

            package_text.append(' ' * 1 * indentation)


        package_text[-1] += 'constant ' + constant_name.upper() + ' : '
        if is_array:
            package_text[-1] += 'T_' + constant_name.upper()
        else:
            if data_type in ('std_logic', 'integer'):
                package_text[-1] += data_type
            else:
                package_text[-1] += data_type + '(' + str(data_w)
                package_text[-1] += ' - 1 downto 0)'
        package_text[-1] += ' := '


        if is_array:
            package_text[-1] += '('
            

        for i in range(array_len):
            data_i = data_dict[constant_name]['data'][i]

            if is_array:
                package_text.append(' ' * 2 * indentation)

            if data_type in 'std_logic':
                package_text[-1] += '\'' + str(data_i) + '\''
            elif data_type in 'integer':
                package_text[-1] += str(data_i)
            elif data_type in ('signed', 'unsigned', 'std_logic_vector'):
                package_text[-1] += '"'
                if isinstance(data_i, str):
                    if len(data_i) > data_w:
                        raise ValueError('Data width is larger that the provided width parameter.')
                    fill_char = (data_i[0] if data_type == 'signed' else '0')
                    package_text[-1] += (data_w - len(data_i)) * fill_char + data_i
                if isinstance(data_i, int):
                    package_text[-1] += int_tobin(data_i, data_w)
                else:
                    raise ValueError('Data type must be binary representation string or int.')
                package_text[-1] += '"'
            else:
                raise ValueError('Type ' +  data_type + ' is not supported yet.')

            if not i == array_len - 1:
                package_text[-1] += ','

        if is_array:
            package_text.append('')
            package_text[-1] += ' ' * 1 * indentation + ')'
        package_text[-1] += ';'
        package_text.append('')


    package_text.append('end ' + package_name + ';')


    with open(file_path, 'w') as f: 
        for line in package_text:
            f.write(line + '\n')



def run_console_command(command):
    try:
        terminal_output = check_output(command, shell=True)
        error = 0
    except CalledProcessError as err:
        terminal_output = err.output
        error = err.returncode
    try:
        terminal_output = terminal_output.decode('utf-8')
    except Exception as e:
        terminal_output = 'Error decoding terminal output.'
    return error, terminal_output



def get_dirs_inside(dir_path):
    scan_folder = os.path.normpath(dir_path)
    return [os.path.abspath(os.path.join(scan_folder, d)) for d in os.listdir(scan_folder) 
           if os.path.isdir(os.path.join(scan_folder, d))]



def get_filepaths_recursive(dir_path, extensions=[], include_files=[], exclude_files=[]):
    scan_folder = os.path.normpath(dir_path)
    file_paths = []

    for root, dirs, files in os.walk(scan_folder):
        for file in files:
            if (not(include_files) or (file in include_files)) and (file not in exclude_files):
                if extensions:
                    for extension in [ext.lower() for ext in extensions]:
                        if file.lower().endswith(extension):
                            file_path = os.path.join(root, file)
                            file_paths.append(file_path)
                else:
                    file_path = os.path.join(root, file)
                    file_paths.append(file_path)
    return file_paths



def get_dirs_containing_files(dir_path, extension=None):
    scan_folder = os.path.normpath(dir_path)
    found_dirs = []
    for root, dirs, files in os.walk(scan_folder):
        for file in files:
            if (not extension) or file.lower().endswith(extension.lower()):
                found_dirs.append(root)
    return found_dirs



def gtkwave_open_wave(ghw_path, gtkw_file=''):
    command_open_wave = 'gtkwave ' + ghw_path
    if gtkw_file:
        command_open_wave += ' -a ' + gtkw_file
    Popen(command_open_wave, stdout=DEVNULL, stderr=STDOUT)
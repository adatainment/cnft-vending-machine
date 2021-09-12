from configparser import ConfigParser

def config(section, filename='vending.ini'):
    # create a parser
    parser = ConfigParser()
    # read config file
    parser.read(filename)

    # get section, default to postgresql
    param_dict = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            param_dict[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return param_dict

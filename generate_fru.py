#!/usr/bin/env python

import sys
import json
import os.path
import collections
import argparse

"""
    Description:
        Purpose of this script is to generate a config xml file containing the
        FRUs of golden configs
"""


def get_dict_from(json_array, k):
    if json_array.has_key(k):
        return json_array[k]
    else:
        return dict()

def json_load(json_file):

    stream = open(json_file, 'r').read()
    json_stream = json.loads(stream)
    return json_stream

def generate_config(d, aobs, golden):
    global pft_xml_output

    fru_value = ['0'] * 20
    for k,v in d.items():
        id = int(aobs[k]["id"], 16)
        aob_id = aobs[k]["module"][v]["id"][2]
        fru_value[id] = aob_id

    config = "".join(fru_value)
    pft_xml_output += "\n<fru_config>\n<name>%s</name>\n<value>%s</value>\n<description>%s</description>\n</fru_config>" % (golden, config, golden)


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Generate fru configurations file.')
	parser.add_argument('aobs_filename', metavar='aobs.json', help='The json file describing AOBs')
	parser.add_argument('configs_filename', metavar='configs.json', help='The json file describing the predefined configurations')
	parser.add_argument('configs_xml', metavar='configs_fru.xml', help='The output file that will receive the list of predefined fru configurations')

	args = parser.parse_args()

	json_aobs = json_load(args.aobs_filename)
	json_configs = json_load(args.configs_filename)

	aobs = get_dict_from(json_aobs, "aobs")
	configs = get_dict_from(json_configs, "configs")

	pft_xml_output = "<fru_configs>"

	try:
	    for k,v in sorted(configs.items()):
		aob_value = get_dict_from(v, "aobs")
		generate_config(aob_value, aobs, k)

	    pft_xml_output += "\n</fru_configs>\n"

	except KeyError, e:
	    print "Key %s does not exist (overriding file malformed)" % str(e)
	    sys.exit(-1)

	goldens_file = open(args.configs_xml, 'w')
	goldens_file.write(pft_xml_output)
	goldens_file.close()

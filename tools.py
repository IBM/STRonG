#!/usr/bin/env python

# 
# Copyright © 2020-2024 IBM Corporation
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 

import argparse
import os
import pathlib
import math
import yaml
import re
import sys

class StrongConfig:
    def __init__(self, args):
        self.defprob = abs(args.default_prob)
        self.defimpt = abs(args.default_impt)
        self.maxpath = args.max_path
        self.stshift = args.structure_shift
        self.ignorescores = args.ignore_score
        self.groupprio = args.group_prio
        self.groupprob = self.GroupCmdToYml(args.group_prob)
        self.pathcutoff = args.cut_off

    def DefaultProb(self):
        return self.defprob
    def DefaultImpact(self):
        return self.defimpt
    def MaxPath(self):
        return self.maxpath
    def IgnoreScores(self):
        return self.ignorescores
    def StructureShift(self):
        return self.stshift
    def GProbOverride(self):
        return self.groupprio
    def GGroupProb(self):
        return self.groupprob
    def PathCutOff(self):
        return self.pathcutoff

    def GroupCmdToYml(self, grstr):
        gdata = {}
        if len(grstr) == 0:
            return gdata
        gel = grstr.split(",")

        for prio,gent in enumerate(gel):
            gpl = gent.split(":")
            gdata[gpl[0]] = (float(gpl[1]), prio)
        return gdata


def cmdline():
    # Parse argument
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="Name of Input file", type=str)
    parser.add_argument("-a", "--antype", help="Path-based or Tree-based analysis [path,tree] (default: path)", default="path", type=str)
    parser.add_argument("-C", "--cut_off", help="Any path with probability below this threshold will be dropped from the calculations (default: none)", default=0.0, type=float)
    parser.add_argument("-D", "--default_prob", help='Set the default node probability in case the yml definition does not specify (default 0.5). NOTE: This disables the search for the normalizing shift value.', default=-0.5, type=float)
    parser.add_argument("-E", "--error", help='Apply random noise profile to node scores', default=0.0, type=float)
    parser.add_argument("-e", "--edge_graph", dest="edge_graph", action='store_const', const=True, help='Convert input to conjugated graph for path analysis', default=False)
    parser.add_argument("-G", "--group_priority", dest="group_prio", action="store_const", const=True, help="Group probabilities take priority over individually specified probabilities (default: False)", default=False)
    parser.add_argument("-g", "--no_graph", dest='no_graph', action='store_const', const=True, help="Skip the display of the graphs and only/directly run the statistics (default: not enabled)", default=False)
    parser.add_argument("-i", "--ignore_score", dest='ignore_score', action='store_const', const=True, help="Ignore the specified node probabilities and use the default node probability instead (default: false)", default=False)
    parser.add_argument("-I", "--default_impt", help='Set the default node impact in case the yml definition does not specify (default 1.0).', default=1.0, type=float)
    parser.add_argument("-M", "--nodemode", help="Print mode of listed nodes (number of paths containing those nodes). Comma-separated list of node names (default: '')", default="", type=str)
    parser.add_argument("-m", "--max_path", help="Maximum number of paths to print in path-based analysis mode (default: 60)", default=60, type=int)
    parser.add_argument("-o", "--output", help="What type of output file format [yml, dot, pgt=python graph-tool] (default=pgt)", default="pgt", type=str)
    parser.add_argument("-P", "--group_prob", help="comma-separated list of cmdline group probability overrides. Any listed entry overwrites the yml spec. Ordering only important for groups that an undefined in yml. This list takes precedence. Format: <group>:<prob>[,<group>:<prob>] (default: "")", default="", type=str)
    parser.add_argument("-s", "--structure_shift", help='Shift node probabilities to normalize for structural differences (default 0.0). NOTE: This does not affect the node labels!', default=-1.0, type=float)
    parser.add_argument("-u", "--unidir", dest='unidir', action='store_const', const=True, help="Links between nodes (within a layer) are made directional (default: false)", default=False)

    return parser.parse_args()


class DataConsistencyError(Exception):
    def __init__(self, message):
        self.message = message

class NameShorteningError(Exception):
    def __init__(self, message):
        self.message = message

# read in all files based off of the main filename
def load_files(fname):
    yml_file_path=os.path.dirname(fname)
    print(fname," is located in directory:",yml_file_path)
    if len(yml_file_path) > 0:
        yml_file_path=yml_file_path+"/"

    ymldata={}
    with open(fname, 'r') as data_stream:
        fdata = yaml.load(data_stream, Loader=yaml.Loader)

        # see whether there are any include files defined
        include_files = fdata.pop("includes",[])
        for iname in include_files:
                print("=====>>> Reading include file:",iname)
                with open(yml_file_path+iname, 'r') as idata_stream:
                    idata = yaml.load(idata_stream, Loader=yaml.Loader)
                    for n,d in idata.items():
                        if n in ymldata:
                            print("Duplicate key ",n,"found in", iname)
                            return None
                        ymldata[n] = d

        for n,d in fdata.items():
            if n in ymldata:
                print("Duplicate key ",n,"found in", fname)
                return None
            ymldata[n] = d

    return ymldata




class Shortener:
    # shorten options
    #  (from_start, end_idx)
    #  from_start: number of chars to use from the beginning of the substrings
    #  end_idx   : index of additional char counted from the end of the substrings (if != 0)
    # example: foxtrail
    #  (3,0)   -> fox
    #  (2,1)  -> fol
    #  (2,2)  -> foi
    #  (2,3)  -> foa
    #  (3,1)  -> foxl
    #  (3,2)  -> foxi
    def __init__(self):
        self.SHORTEN_OPTIONS=[(3,0), (2,1), (2,2), (3,1), (2,3), (3,2), (32,0)]
        self.shortener=0

    def getOptionCount(self):
        return len(self.SHORTEN_OPTIONS)

    def get(self):
        return self.shortener

    def set(self, shortener=-1):
        self.shortener=min( max(0, shortener), len(self.SHORTEN_OPTIONS) )

    def explain(self):
        opt=self.SHORTEN_OPTIONS[ self.shortener ]
        extrachar=""
        if opt[1] != 0:
            POSTFIXES=["th","st","nd","rd"]
            postfix=0
            if opt[1] % 10 < 4:
                postfix=opt[1] % 10
            extrachar="and then adds the "+str( opt[1] )+POSTFIXES[postfix]+" char from the end"
        return "Shortening uses the first "+str(opt[0])+" chars "+extrachar+" of the substring."

    def apply(self, longname, option=-1):
        if option==-1:
            option = self.get()
        rs=""
        naidx=re.split('[\.]', longname)

        opt=self.SHORTEN_OPTIONS[option]
        for sw in naidx:
            if len(rs) > 0:
                rs=rs+"_"

            ab=min(opt[0], len(sw))
            ec=''
            if opt[1] != 0:
                ec=sw[min( len(sw)-opt[1], len(sw) )]
            rs=rs+sw[0:ab]+ec
        return rs

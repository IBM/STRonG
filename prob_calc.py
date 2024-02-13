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


from graph_tool.all import *
import statistics
import numpy
import math

from constants import DEFAULT_PROBABILITY, DEFAULT_IMPACT


class prob_calculator:
    def __init__(self, sg, args):
        self.sg = sg
        self.ignore_score = args.ignore_score
        self.with_errors = (args.error != 0.0)
        self.default_prob = abs(args.default_prob)
        self.default_impt = abs(args.default_impt)
        self.path_cutoff = min(1.0, abs(args.cut_off))
        # the default arg is -0.5 in case the cmd line arg is not present
        # do not any shifting if default prob is requested by cmdline
        self.no_shift = (args.default_prob >= 0.0) or (args.structure_shift > -1.0)
        self.detected_shift = 0.0

        if args.structure_shift == -1.0: # cmdline '-s x' not provided
            self.args_shift = 0.0
        else:
            self.args_shift = args.structure_shift
            self.detected_shift = args.structure_shift

    def path_prob(self, path, shift):
        prob = 1.0
        if self.ignore_score and not self.with_errors:
            nprob = max(0.0, min( (self.default_prob + shift), 1.0))
            prob = (nprob)**(len(path)-1)
            # print("Pathprob:",prob, [ self.default_prob+shift for x in path ])
        else:
            for i in path[1:]:
                prob = prob * max(0.0, min( ( self.sg.vertex_probability[i] + shift ), 1.0 ))
            # print("Pathprob:",prob, [ self.sg.vertex_probability[x]+shift for x in path ])
        if prob < self.path_cutoff:
            prob = 0.0
        return prob

    def path_risk(self, path, shift, debug=False):
        prob = 1.0
        impt = 0.0
        risk = 0.0
        if self.ignore_score and not self.with_errors:
            nprob = max(0.0, min( (self.default_prob + shift), 1.0))
            prob = (nprob)**(len(path)-1)
            for i in path[1:]:
                impt = impt + (self.sg.vertex_impact[i] * math.sqrt( self.sg.get_vertices()[i].out_degree()))
                risk = risk + nprob * impt
                if debug:
                    print("PRisk[",i,"]=",impt," <-- ",self.sg.vertex_impact[i]," * ",self.sg.get_vertices()[i].out_degree())
        else:
            for i in path[1:]:
                prob = prob * max(0.0, min( ( self.sg.vertex_probability[i] + shift ), 1.0 ))
                impt = impt + (self.sg.vertex_impact[i] * math.sqrt( self.sg.get_vertices()[i].out_degree()))
                risk = risk + prob * impt
                if debug:
                    print("PRisk[",i,"]=",impt," <-- ",self.sg.vertex_impact[i]," * ",self.sg.get_vertices()[i].out_degree())

        if prob < self.path_cutoff:
            prob = 0.0
            impt = 0.0
            risk = 0.0
        return (prob, impt, risk)


    # used to find the shift normalization parameter
    def default_P_total(self, paths, default_prob=DEFAULT_PROBABILITY):
        #path probabilities of all paths
        list_prob=[]
        for path in paths:
            list_prob.append( 1 - (default_prob)**len(path) )

        #Union of path probabilities
        return 1.0 - numpy.prod(list_prob)

    def find_shift(self, paths):
        if self.no_shift:
            return self.args_shift

        shift=0.0
        eps = 0.5
        old_eps = self.default_P_total(paths, default_prob=0.5) - 0.5
        prev_shift_delta = -0.25
        iter=0
        while abs(eps) > 0.0001 and iter < 20:
            shift = shift + prev_shift_delta
            eps=self.default_P_total(paths, default_prob=0.5+shift) - 0.5
            print("find_shift: o{}\te{}\ts{}\td{}".format(old_eps, eps, shift, prev_shift_delta))

            if abs(eps) > abs(old_eps) and eps * old_eps >= 0.0:
                # if eps increases, we're moving in the wrong direction
                prev_shift_delta = -prev_shift_delta
            elif abs(eps) < abs(old_eps) and eps * old_eps >= 0.0:
                # both eps on 'same side of curve' -> keep moving, just slower
                prev_shift_delta = prev_shift_delta / 2.0
            else:
                # eps's on 'different sides of curve' -> cut delta in half and change dir
                prev_shift_delta = -prev_shift_delta / 2.0

            old_eps = eps
            iter=iter+1

        if iter >= 20:
            print("WARNING: Unable to converge to find shift normalization")
        else:
            print("Found normalization shift: ",shift," after ",iter,"iterations")
        self.detected_shift = shift
        return self.args_shift

    def getshift(self):
        return self.detected_shift

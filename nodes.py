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

import os
import pathlib
import yaml

from constants import DEFAULT_PROBABILITY,DEFAULT_IMPACT
import tools
import layers
import groups as gr


class Node:
    def __init__(self, name, data, layers, groups, config):
        NODE_REQUIRED=["layer","links"]
        NODE_DEFAULTS={"layer":"none",
                       "links":[],
                       "groups":[],
                       "probability":-1.0,
                       "impact":1.0,
                       "comment":""}

        # todo: lowercase for all layer name references

        self.name = name
        for key,default in NODE_DEFAULTS.items():
            if key not in data:
                setattr(self, key, NODE_DEFAULTS[key])
            else:
                setattr(self, key, data[key])
        print("NODE:",self.name,"Probability:",self.probability)

        self.setlref( layers.find( self.nlayer() ) )
        self.activegroup = None
        if self.groups:
            self.setactivegroup( groups, config.GProbOverride() )

        self.adjustprobability(config)
        self.adjustimpact(config)


    def setlref(self, lref=None):
        self.lref = lref
        self.name = self.lref.lname() + "." + self.name

    def setactivegroup(self, groups, gprob_override):
        gprio = 1000000
        for gg in self.groups:
            gobj = groups.find(gg)
            if gobj and gprio>gobj.gpriority():
                print("GROUP: member of:",gobj.gname(), "; Priority:",gobj.gpriority())
                self.activegroup = gobj
                gprio = gobj.gpriority()
        if self.activegroup != None:
            print("INFO: GROUP setting active group {}".format(self.activegroup.gname()) )
            if gprob_override == True:
                self.probability = self.activegroup.gprobability()

    def adjustprobability(self, config):
        if config.IgnoreScores():
            self.probability = config.DefaultProb()
            self.impact = config.DefaultImpact()
            return

        if config.GProbOverride() and self.activegroup != None:
            self.probability = self.activegroup.gprobability()
            self.impact = self.activegroup.gimpact()
            return

        if self.probability == -1.0:
            if self.activegroup != None:
                self.probability = self.activegroup.gprobability()
            else:
                self.probability = config.DefaultProb()
            return
        if self.impact == -1.0:
            if self.activegroup != None:
                self.impact = self.activegroup.gimpact()
            else:
                self.impact = config.DefaultImpact()
            return

    def adjustimpact(self, config):
        if config.IgnoreScores():
            self.impact = config.DefaultImpact()
            return
        # no further adjustments for now (group-impact is not yet implemented)

    def nname(self):
        return self.name
    def nlinks(self):
        return self.links
    def ngroups(self):
        return self.groups
    def nactivegroup(self):
        return self.activegroup
    def nprobability(self):
        return self.probability
    def nimpact(self):
        return self.impact
    def nlayer(self):
        return self.layer
    def nlayerref(self):
        return self.lref
    def linkdestlist(self):
        return [ l["d"] for l in self.links ]
    def fixlinkdest(self, link_map):
        for l in self.links:
            print(self.nname()," --> ", l["d"])
            if l["d"] in link_map:
                print(self.nname(),": Remapping link: ",l["d"],"to",link_map[ l["d"] ])
                l["d"] = link_map[ l["d"] ]


class NodeList:
    def __init__(self):
        self.nodes = []

    def add(self, name, ndata, layers, groups, config):
        newnode = Node(name, ndata, layers, groups, config)
        self.nodes.append( newnode )
        return newnode

    def add_node(self, node):
        self.nodes.append( node )

    def check_consistency(self, layers):
        # collect node list for easier existence check
        nlist = [ n.nname() for n in self.nodes ]

        passed=True
        for n in self.nodes:

            # make sure probabilities are within range
            if n.nprobability() < 0.0 or n.nprobability() > 1.0:
                msg="Probability out of range. {} not in [0.0 : 1.0]".format(n.nprobability())
                passed=False

            # impact range 1.0..4.0 and 0.0 for iso layer nodes
            if (n.nimpact() < 1.0 and n.nimpact != 0.0) or n.nimpact() > 4.0:
                msg="Impact Score out of range. {} not in [1.0 : 4.0]".format(n.impact())
                passed=False

            # check for any link destinations that point to non-existing nodes
            for l in n.nlinks():
                if l["d"] not in nlist:
                    msg = "unknown link destination "+l["d"]
                    passed = False
                    break
                if "p" in l and (l["p"] < 0.0 or l["p"] > 1.0):
                    msg = "link probability for {} out of range. {} not in [0.0 : 1.0]".format(l["d"], l["p"])
                    passed = False
                    break

            # make sure the node references a layer that exists
            if layers != None:
                if not layers.find(n.nlayer()):
                    msg="No layer definition found for {}".format(n.nlayer())
                    passed = False

            if not passed:
                raise tools.DataConsistencyError("INCONSISTENCY: NODE:{}: {}".format(n.nname(), msg))


    def get(self):
        return self.nodes

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


import copy

import layers
import groups
import nodes
import stencil


class StrongGraph:
    def __init__(self, ymldata, config):
        self.layers = layers.LayerList()
        self.nodes = nodes.NodeList()
        self.stencils = stencil.StencilList()
        self.nodes_dict = {}
        self.config = config

        self.attacker = ymldata.pop("attacker",[])
        self.target = ymldata.pop("target",[])
        gdata = ymldata.pop("groups",[])
        self.groups = groups.StrongGroups(gdata, config.GGroupProb())
        self.cmap = {}

        # first pass over data to create layers and stencils
        for n,d in ymldata.items():
            if "type" in d:
                if d["type"].lower() == "layer":
                    self.layers.add(n, d)
                elif d["type"].lower() == "stencil":
                    self.stencils.add(n, d)
                else:
                    print("Unrecognized Type:", d["type"])

        # second pass over data to create nodes
        for n,d in ymldata.items():
            if "type" in d:
                continue
            else:
                if "stencil" in d:
                    snodes = self.instantiate(n,d)
                    for sn in snodes.get():
                        self.nodes.add_node(sn)
                else:
                    self.nodes.add(n, d, self.layers, self.groups, config)

        # fix/update any links that might need to be remapped because of modified/collapsed stencils
        print("LINK UPDATES ====================")
        for n in self.nodes.get():
            n.fixlinkdest( self.cmap )

        self.layers.log()
        print("NodeList:")
        for n in self.nodes.get():
            print("Node:",n.nname()," ---> ",n.nlinks()," | ",n.nactivegroup())
            self.nodes_dict[n.nname()] = n
        self.check_consistency()


    def get_nodes(self):
        return self.nodes
    def get_layers(self):
        return self.layers

    def get_attackers(self):
        return self.attacker
    def get_targets(self):
        return self.target

    def is_attacker(self, name):
        return name in self.attacker
    def is_target(self, name):
        return name in self.target

    def shorten_ta_names(self, shortener):
        if "." in self.attacker[0]:
            self.attacker = [ shortener.apply( n ) for n in self.attacker ]
        if "." in self.target[0]:
            self.target = [ shortener.apply( n ) for n in self.target ]

    # create instance links dictionary for all external links
    # such that linklist[subnode] returns a list of those links
    # ready to insert into the stencil instance
    def extract_external_links(self, ndata):
        linklist = {}
        if "links" in ndata:
            for li in ndata["links"]:
                if li["s"] not in linklist:
                    linklist[ li["s"] ] = []
                link_entry = { k:v for (k,v) in li.items() if k != "s" }
                if link_entry["d"] in self.cmap:
                    print("ReMapping outbound link:", link_entry["d"] )
                    link_entry["d"] = self.cmap[ link_entry["d"] ]
                linklist[ li["s"] ].append( link_entry  )

        return linklist

        # # remove any links pointing at deleted nodes (listed in snode_remove)
        # for n,d in snodes.items():
        #     d["links"]=[ l for l in d["links"] if l["d"] not in snode_remove ]



    # instantiate the intra-stencil links
    def instantiate_links(self, srcnode, node, instancename, removed):
        instlinks = []
        if "links" in node:
            print("Link Instantiation for: ", srcnode)
            nameprefix = node["layer"] + "." + instancename + "."
            for dest in node["links"]:
                print("link to",dest)
                if dest in removed:
                    print("SKIPPING removed destination snode", dest)
                    continue
                if nameprefix+dest["d"] in self.cmap:
                    tnode = self.cmap[ nameprefix+dest["d"] ]
                else:
                    tnode = node["layer"] + "." + instancename + "." + dest["d"]
                newlink = dest
                newlink["d"] = tnode
                instlinks.append(newlink)
        return instlinks

    def process_modifiers(self, instencil, ndata):
        stencil = copy.deepcopy(instencil)

        # deletion updates
        # renaming updates
        # problem: node rename/deletion doesn't update link-names
        snode_remove = []
        modifiers = {}
        if "modifier" in ndata:
            modlist = ndata["modifier"]
            for e in modlist:
                for k,v in e.items():
                    modifiers[ k ] = v
                    if len(v) == 0:
                        print("stencil node '{}' will be removed by modifier".format(k))
                        snode_remove.append(k)
        else:
            return stencil.sdata(),snode_remove

        snodes = {}
        print("Processing modifiers for stencil:", stencil.sname())
        for snode,sdata in stencil.sdata().items():
            if snode in modifiers:
                # if instance has a modifier for this stencil node:
                for mdata in modifiers[snode]:
                    if "n" in mdata:
                        nname = mdata["n"] # return and remove the "n" entry from modifier data
                    else:
                        nname = snode
                    snodes[ nname ] = {}
                    if "p" in mdata:
                        snodes[ nname ]["probability"] = mdata["p"]
                    if "i" in mdata:
                        snodes[ nname ]["impact"] = mdata["i"]
                    if "g" in mdata:
                        if type(mdata["g"]) is str:
                            snodes[ nname ]["groups"] = [ mdata["g"] ]
                        else:
                            snodes[ nname ]["groups"] = mdata["g"]


                    snodes[nname]["links"] = []
                    for link in sdata["links"]:
                        if link["d"] in snode_remove:
                            continue
                        if link["d"] in modifiers:
                            for newlink in modifiers[ link["d"] ]:
                                link_entry = link.copy()
                                link_entry["d"] = newlink["n"]
                                snodes[nname]["links"].append(link_entry)
                        else:
                            snodes[nname]["links"].append(link.copy())

                    # snodes[ nname ]["links"] = [ l.copy() for l in sdata["links"] if l["d"] not in snode_remove ]

            else:
                snodes[snode] = { k:v.copy() for (k,v) in sdata.items() if k != "links" }
                snodes[snode]["links"] = []
                for link in sdata["links"]:
                    if link["d"] in modifiers:
                        for newlink in modifiers[ link["d"] ]:
                            link_entry = link.copy()
                            link_entry["d"] = newlink["n"]
                            snodes[snode]["links"].append(link_entry)
                    else:
                        snodes[snode]["links"].append(link.copy())

        for n,v in snodes.items():
            print(n, v)
        return snodes,snode_remove

    # create a collapsed node, remove collapsed subnodes from stencil items
    # collect node-to-collapsed node mappings for links
    def process_collapsed(self, nametup, ndata, stencilnodes, linklist):
        nameprefix=nametup[0]+"."+nametup[1]+"."
        cnodename=nametup[2]

        collapsed = "collapsed" in ndata and len( ndata["collapsed"] ) > 0
        if collapsed:
            # todo: check connectivity (can only collapse connected nodes)
            for cn in ndata["collapsed"]:
                self.cmap[nameprefix+cn] = nameprefix+cnodename
            print(self.cmap)
            remaining = {}

            # create the collapsed node
            cnode={}
            cnode["layer"] = ndata["layer"]
            cnode["links"] = []
            remaining[cnodename] = cnode

            uniquedest = set()
            for sn,sd in stencilnodes.items():
                if sn not in ndata["collapsed"]:
                    remaining[sn] = sd
                else:
                    # internal links updates: destinations
                    for l in sd["links"]:
                        if nameprefix+l["d"] not in self.cmap:
                            newlink = copy.deepcopy( l )
                            if newlink["d"] in uniquedest:
                                continue
                            uniquedest.add(l["d"])
                            newlink["s"] = cnodename
                            cnode["links"].append( newlink )
                            print("creating new internal link based on",sn,"to", newlink)
            linklist[ cnodename ] = []

            # external link updates: sources
            for ln,ld in linklist.items():
                if nameprefix+ln in self.cmap:
                    for l in ld:
                        newlink = copy.deepcopy( l )
                        if newlink["d"] in uniquedest:
                            continue
                        uniquedest.add(l["d"])
                        newlink["s"] = cnodename
                        print("Updated external link: ", ln, " sourced:", cnodename)
                        linklist[ cnodename ].append( newlink )

            if "cprobability" in ndata:
                cnode["probability"] = ndata["cprobability"]
            if "cimpact" in ndata:
                cnode["impact"] = ndata["cimpact"]
            if "groups" in ndata:
                cnode["groups"] = ndata["groups"]

            # without cprobability, make this equal a regular node without prob setting
            # ... later there should be considerations of:
            # TODO: weighted average of collapsed nodes?

            # else:
            #     cnode["probability"] = self.config.DefaultProb()

            return cnode, remaining
        return None, stencilnodes


    def instantiate(self, name, ndata):
        if ndata["stencil"] not in self.stencils.get():
            print("Requested stencil ", ndata["stencil"], "not (yet) known. Make sure stencil is defined before instantiation")
            return

        linklist = self.extract_external_links(ndata)

        # instantiate the stencil
        stencil = self.stencils.get()[ ndata["stencil"] ]
        snode_list = nodes.NodeList()

        modified,removed = self.process_modifiers(stencil, ndata)
        modout = ""
        if "modifier" in ndata:
            modout = "with modifiers"

        # probability taken from the stencil/node instance data
        nprob = None
        if "probability" in ndata:
            nprob = ndata["probability"]
        # impact taken from the stencil/node instance data
        nimpt = None
        if "impact" in ndata:
            nimpt = ndata["impact"]

        cnode,modified = self.process_collapsed( (ndata["layer"], name, "grouped"),
                                                 ndata,
                                                 modified,
                                                 linklist )

        print("Instantiating stencil '{}' as '{}' {}".format(ndata["stencil"], name, modout) )
        for snode,sdata in modified.items():
            print("Instantiating NODE:", snode)
            newnode = copy.deepcopy(sdata)  # make sure the stencil data is replicated from the original
            newnode["layer"] = ndata["layer"]

            if "probability" in sdata:
                newnode["probability"] = sdata["probability"]
            elif nprob != None:
                newnode["probability"] = nprob

            if "impact" in sdata:
                newnode["impact"] = sdata["impact"]
            elif nimpt != None:
                newnode["impact"] = nimpt

            if "groups" in ndata:
                newnode["groups"] = ndata["groups"]

            instlinks = self.instantiate_links(snode, newnode, name, removed)

            if snode in linklist:
                nodelinks = linklist[snode]
            else:
                nodelinks = []

            newnode["links"] = instlinks + nodelinks
            newnodename = name + "." + snode
            # print("Stencil:", stencil.sname(), " creating: ", newnodename, newnode)
            snode_list.add(newnodename, newnode, self.layers, self.groups, self.config)

        return snode_list

    def check_consistency(self):
        self.nodes.check_consistency(self.layers)

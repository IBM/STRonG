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
import os
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, desc="None"):
        return it


from constants import N1,N2,DEFAULT_PROBABILITY,DEFAULT_IMPACT,STRUCTURAL_SHIFT,MAX_PATHS,CVSS_CONF,CVSS_INT,CVSS_AVAIL,PNORM_BINS, PNORM_PEAK
import tools
import layers
import nodes
import stencil
import graph as sgr
import prob_calc as pc


class sec_graph:
    def __init__(self, data):
        self.lg = data
        self.shortener = tools.Shortener()
        self.g = Graph()
        self.vertex_label = self.g.new_vertex_property("string")
        self.vertex_fill_color = self.g.new_vertex_property('vector<double>')
        self.vertex_probability = self.g.new_vertex_property("double")
        self.vertex_impact = self.g.new_vertex_property("double")
        self.vertex_size = self.g.new_vertex_property("int")
        self.node_index = self.g.new_vertex_property("int") # index into nodelist
        self.g.vertex_properties['vertex_fill_color']=self.vertex_fill_color
        self.g.vertex_properties['vertex_probability']=self.vertex_probability
        self.g.vertex_properties['vertex_impact']=self.vertex_impact
        self.g.vertex_properties['vertex_size']=self.vertex_size
        self.g.vertex_properties['node_index']=self.node_index

        self.targ_nodes=[]
        self.attk_nodes=[]


    def get_nodes(self):
        return self.lg.get_nodes()
    def get_vertices(self):
        return list(self.g.vertices())

    def get_attackers(self):
        return self.attk_nodes
    def get_targets(self):
        return self.targ_nodes

    def create_labels(self):
        shopt=-1
        for opt in range( self.shortener.getOptionCount() ):
            retry = False
            shlist=[]
            for n in self.get_nodes().get():
                nshort=self.shortener.apply(n.nname(), opt)
                if nshort in shlist:
                    print("SHORT-NAME COLLISION with option", opt,": ", n.nname(), nshort)
                    retry = True
                    break
                shlist.append(nshort)
            if retry == False:
                shopt=opt
                break
        if shopt==-1:
            raise tools.NameShorteningError("NO MORE SHORTENING OPTIONS AVAILABLE TO CREATE UNIQUE SHORTNAMES")

        print("Successful SHORTENING with option", shopt,": ", shlist)
        self.shortener.set(shopt)
        self.lg.shorten_ta_names(self.shortener)

    def explain_labels(self):
        print(self.shortener.explain())

    def find_node(self, longname):
        name = self.shortener.apply(longname)
        for i,n in enumerate(self.vertex_label):
            if name in n:
                return i

    def edge_dedup(self, edgelist, sshort, dshort, unidir=False):
        esorted=[sshort, dshort]

        if not unidir:
            esorted.sort()

        v1=esorted[0]
        v2=esorted[1]
        if v1 not in edgelist:
            edgelist[v1]=[]
        if v2 not in edgelist[v1]:
            edgelist[v1].append(v2)
            print("New Edge:", v1, v2)
            return edgelist,True
        return edgelist,False


    def generate_graph(self, unidir=False):
        self.create_labels()
        edges={}
        self.targ_nodes=[]
        self.attk_nodes=[]

        # create the vertices
        for idx,n in enumerate( self.get_nodes().get() ):
            nshort=self.shortener.apply( n.nname() )

            locals()[nshort] = self.g.add_vertex()
            self.vertex_label[locals()[nshort]] = nshort+"."+str(n.nprobability())
            self.vertex_probability[locals()[nshort]] = n.nprobability()
            self.vertex_impact[locals()[nshort]] = n.nimpact()
            self.node_index[locals()[nshort]] = idx
            if self.lg.is_attacker(nshort):
                self.attk_nodes.append(locals()[nshort])
            if self.lg.is_target(nshort):
                self.targ_nodes.append(locals()[nshort])

        for n in self.get_nodes().get():
            nshort=self.shortener.apply( n.nname() )
            for l in n.nlinks():
                dshort=self.shortener.apply( l["d"] )
                edges,newedge = self.edge_dedup(edges, nshort, dshort, unidir)
                if newedge:
                    self.g.add_edge(locals()[nshort], locals()[dshort])
                    if not unidir:
                        self.g.add_edge(locals()[dshort], locals()[nshort])

    def conjugate(self):

        self.targ_nodes=[]
        self.attk_nodes=[]

        self.cg = Graph()
        self.cgv_label = self.cg.new_vertex_property("string")
        self.cgv_probability = self.cg.new_vertex_property("double")
        self.cgv_impact = self.cg.new_vertex_property("double")
        self.cgv_index = self.cg.new_vertex_property("int") # index into edgelist
        self.cgv_color = self.cg.new_vertex_property("vector<double>")
        self.cgv_enodes_labels = self.cg.new_edge_property("string")
        self.cg.vertex_properties['cgv_label']=self.cgv_label
        self.cg.vertex_properties['cgv_probability']=self.cgv_probability
        self.cg.vertex_properties['cgv_impact']=self.cgv_impact
        self.cg.vertex_properties['cgv_index']=self.cgv_index
        self.cg.vertex_properties['vertex_fill_color']=self.cgv_color
        self.cg.edge_properties['cgv_enodes_labels']=self.cgv_enodes_labels

        for s, t, i in self.g.iter_edges([self.g.edge_index]):
            str_i = "e"+str(i)
            locals()[str_i] = self.cg.add_vertex()
            self.cgv_label[locals()[str_i]] = str_i
            self.cgv_probability[locals()[str_i]] = self.vertex_probability[t]
            self.cgv_impact[locals()[str_i]] = self.vertex_impact[t]
            self.cgv_index[locals()[str_i]] = i
            dot_idx=self.vertex_label[s].index('.')
            if self.lg.is_attacker(self.vertex_label[s][:dot_idx]):
                self.attk_nodes.append(locals()[str_i])
            dot_idx=self.vertex_label[t].index('.')
            if self.lg.is_target(self.vertex_label[t][:dot_idx]):
                self.targ_nodes.append(locals()[str_i])

        # connect 2 edges if the target of edgeA equals the source of edgeB
        #  - iterate over edges e of g
        #  - create edge in cg to all outbound edges of the target(e)
        #  - label the edge with the shared vertex
        for s, t, i in self.g.iter_edges([self.g.edge_index]):
            str_i = "e"+str(i)
            # print(s,t,i, self.vertex_label[s], self.vertex_label[t])
            for st, tt, ei in self.g.iter_out_edges(t, [self.g.edge_index]):
                # print("   ",st,tt, ei, self.vertex_label[st], self.vertex_label[tt])
                str_ei = "e"+str(ei)
                loc_e = str_i+str_ei
                locals()[loc_e] = self.cg.add_edge(locals()[str_i], locals()[str_ei])
                self.cgv_enodes_labels[locals()[loc_e]] = self.vertex_label[t]


        for v in self.cg.vertices():
            p=self.cgv_probability[v]
            self.cgv_color[v] = (p, 0/255.0, 0/255.0, 1)

        finode=self.cg.add_vertex()
        self.cgv_label[finode]="fin"
        self.cgv_probability[finode]=1.0
        self.cgv_impact[finode]=DEFAULT_IMPACT
        self.cgv_index[finode]=finode
        for e in self.targ_nodes:
            str_e="e"+str(e)
            finedge=self.cg.add_edge(locals()[str_e], finode)
            self.cgv_enodes_labels[finedge] = "fin"
        self.targ_nodes=[finode]

        print(self.g)
        print(self.cg)
        # print(self.targ_nodes, self.attk_nodes)

        # replace g with cg
        self.g = self.cg
        self.vertex_label = self.cgv_label
        self.vertex_fill_color = self.cgv_color
        self.vertex_probability = self.cgv_probability
        self.vertex_impact = self.cgv_impact
        self.node_index = self.cgv_index

        # out_deg = self.g.degree_property_map("out")
        # deg = prop_to_size(out_deg, mi=20, ma=60)
        # graph_draw(self.g,
        #            vertex_size=deg,
        #            vertex_text=self.cgv_label,
        #            vertex_font_size=14,
        #            # vertex_fill_color=self.cg.vertex_properties['vertex_fill_color'],
        #            vertex_pen_width=0.0,
        #            vertex_text_out_width=0.0,
        #            # vertex_text_position=5.0,
        #            # vertex_text_offset=[-0.01,0.005],
        #            edge_pen_width=3,
        #            edge_color=(180/255.0,180/255.0,180/255.0, 1),
        #            edge_text=self.cgv_enodes_labels,
        #            output_size=[1500,1000])


    def draw(self, vsize=15, fsize=14, osize=[1500,1000], target=None, sources=[]):
        for v in self.g.vertices():
            p=self.vertex_probability[v]
            self.vertex_fill_color[v] = (p, 0/255.0, 0/255.0, 1)
            if v == target:
                self.vertex_fill_color[v] = (0/255, 200/255.0, 0/255.0, 1)
            if v in sources:
                self.vertex_fill_color[v] = (0/255, 0/255.0, 200/255.0, 1)

        # out_deg = self.g.degree_property_map("out")
        # deg = prop_to_size(out_deg, mi=20, ma=60)
        deg = prop_to_size(self.g.vertex_properties["vertex_impact"], mi=20, ma=60)
        graph_draw(self.g,
                   vertex_size=deg,
                   vertex_text=self.vertex_label,
                   vertex_font_size=14,
                   vertex_fill_color=self.g.vertex_properties['vertex_fill_color'],
                   vertex_pen_width=0.0,
                   vertex_text_out_width=0.0,
                   vertex_text_position=5.0,
                   vertex_text_offset=[-0.01,0.005],
                   edge_pen_width=3,
                   edge_color=(180/255.0,180/255.0,180/255.0, 1),
                   output_size=osize)

    def blast_radius_draw(self, paths):
        self.eset = self.g.new_edge_property("bool", val=False)
        self.g.edge_properties['bref']=self.eset
        self.vset = self.g.new_vertex_property("bool", val=False)
        self.g.vertex_properties['bref']=self.vset

        for p in paths:
            snode = p[0]
            self.vset[ snode ] = True
            for v in p[1:]:
                # print(v, self.vset[v])
                self.vset[ v ] = True
                self.eset[ self.g.edge(snode, v) ] = True
                snode = v
                # self.vset[ t ] = True
                # self.eset[ i ] = True

        brg = GraphView(self.g, vfilt=self.vset, efilt=self.eset)
        graph_draw(brg,
                   vertex_size=20,
                   vertex_text=self.vertex_label,
                   vertex_font_size=14,
                   vertex_fill_color=(220/255, 0, 0, 1),
                   vertex_pen_width=0.0,
                   vertex_text_out_width=0.0,
                   vertex_text_position=5.0,
                   vertex_text_offset=[-0.01,0.005],
                   edge_pen_width=3,
                   edge_color=(180/255.0,180/255.0,180/255.0, 1),
                   output_size=[1500,1000])


def find_modes(paths, nodes):
    nhist={}
    first=[]
    second=[]
    third=[]
    for n in range(0, len(nodes)):
        nhist[n] = 0
    for p in tqdm(paths, desc="PathModes"):
        for n in p[1:-1]:
            nhist[n] = nhist[n]+1

    fst_val = [0,0,0]
    for n,c in nhist.items():
        if c > fst_val[0]:
            fst_val[0] = c
        elif c > fst_val[1]:
            fst_val[1] = c
        elif c > fst_val[2]:
            fst_val[2] = c

    # find the 3 highest values in the dict
    hvals = [ c for (n,c) in nhist.items() ]
    fst_val[0] = max(hvals)
    hvals = [ n for n in hvals if n < fst_val[0] ]
    fst_val[1] = max(hvals)
    hvals = [ n for n in hvals if n < fst_val[1] ]
    fst_val[2] = max(hvals)

    for n,c in nhist.items():
        if c == fst_val[0]:
            first.append(n)
        if c == fst_val[1]:
            second.append(n)
        if c == fst_val[2]:
            third.append(n)

    return (nhist, fst_val, first, second, third)

def has_loop(path):
    return len(path) != len(set(path))

def path_stats(sg, N1, N2, args):
    mode_of_nodes_list = []
    if args.nodemode != '':
        mode_of_nodes_list = [ sg.find_node(i) for i in args.nodemode.split(',') ]
    shift=0.0
    dropped_paths = 0
    print(mode_of_nodes_list)
    if args.edge_graph == True:
        sg.conjugate()
        print("Attackers:",[ sg.cgv_label[x] for x in sg.get_attackers() ])
        print("Targets  :",[ sg.cgv_label[x] for x in sg.get_targets() ])
    if args.error != 0.0:
        nodelist = sg.get_nodes().get()
        print("Applying ",args.error,"% of noise to scores to ",len(nodelist)," nodes")
        applied_err=abs(args.error)
        addsub=math.copysign(1.0, args.error)
        noise=numpy.random.normal(0.0, numpy.sqrt(applied_err), len(nodelist))
        print(sg.vertex_probability.get_array())
        for n in range(0, len(nodelist)):
            ridx=numpy.random.randint(len(nodelist))
            sg.vertex_probability[n] = min(1.0, max(sg.vertex_probability[n] + addsub*noise[ridx]/100.0, 0.0))
            iidx=numpy.random.randint(len(nodelist))
            sg.vertex_impact[n] = min(4.0, max(sg.vertex_impact[n] + addsub*noise[iidx]/100.0, 0.0))
        print(sg.vertex_probability.get_array())

    # create a new probability calculator
    pcalc=pc.prob_calculator(sg, args)
    for c in sg.get_targets():
        ap = []
        print("Detecting paths...")
        for a in sg.get_attackers():
            cutoff=max( 50, int( float( len( sg.get_nodes().get())) *0.85 ))
            ap.extend( all_paths(sg.g, a, c, cutoff=cutoff, edges=False) )

        if len(ap)<2:
            if len(ap) > 0:
                print(ap[0])
            print("Only {} paths found. Can't perform statistics on that".format(len(ap)) )
            if not args.no_graph:
                sg.draw(vsize=15, fsize=16, osize=[1500,1000], target=c, sources=sg.attk_nodes)
            continue

        # shift finder with all paths because path_prob may depend on detected shift
        shift = pcalc.find_shift(ap)

        #path probabilities of all paths and cut-off filtering
        list_prob=[]
        list_impt=[]
        list_vrisk=[]
        list_prisk=[]
        filtered_ap=[]
        replace_ap = False
        print("calculating path probabilities...")
        for path in tqdm(ap, desc="PathProbs"):
            if not has_loop(path):
                (pprob, pimpt, risk) = pcalc.path_risk(path, shift)
                if pprob >= args.cut_off:
                    list_prob.append(pprob)
                    list_impt.append(pimpt)
                    list_vrisk.append(risk)
                    list_prisk.append(pprob * pimpt)
                    filtered_ap.append(path)
                else:
                    dropped_paths = dropped_paths + 1
                    replace_ap = True
            else:
                print("THIS PATH HAS A LOOP:",path)
        if replace_ap == True:
            ap = filtered_ap

        print("processing path lengths...")
        lengths = [len(i) for i in ap]

        # count paths through nodes to use as vertex size
        # for n in range(0, len(sg.get_nodes().get())):
        #     sg.vertex_paths[n] = 1.0
        # for p in ap:
        #     for n in p:
        #         sg.vertex_paths[n] = sg.vertex_paths[n]*1.01
        # for n in range(0, len(sg.get_nodes().get())):
        #     sg.vertex_paths[n] = math.log(sg.vertex_paths[n])
        # print([ sg.vertex_paths[n] for n in range(0, len(sg.get_nodes().get())) ])

        minplen=min(lengths)
        maxplen=max(lengths)
        spa=[]
        lpa=[]
        for x in ap:
            if len(x) == minplen:
                spa.append(x)
            if len(x) == maxplen:
                lpa.append(x)
        # spa=[x for x in ap if len(x)==minplen]
        # lpa=[x for x in ap if len(x)==maxplen]

        print("---------shortest{}/{} paths-------------".format(MAX_PATHS,len(ap)))
        for path in spa[0:MAX_PATHS]:
            print([sg.vertex_label[m] for m in path], pcalc.path_risk(path, shift))

        print("---------first{}/{} paths-------------".format(MAX_PATHS,len(ap)))
        for path in sorted(ap[0:MAX_PATHS], key=len):
            print([sg.get_nodes().get()[ sg.node_index[m] ].nname() for m in path[1:]], pcalc.path_risk(path, shift))

        print("-----------longest paths-------------")
        for path in lpa[0:MAX_PATHS]:
            print([sg.vertex_label[m] for m in path], pcalc.path_risk(path, shift))

        #Path statistics
        print("calculating mean PL...")
        mean = statistics.mean(lengths)
        print("calculating stdev of PL...")
        stdev = statistics.stdev(lengths)
        print("calculating median of PL...")
        median = statistics.median(lengths)
        print("calculating modes of nodes in paths...")
        (nhist, fst_val, first, second, third) = find_modes(ap, sg.get_vertices())
        # print(nhist)

        sg.explain_labels()
        print("=============================================================")
        print("Critical node = ",sg.vertex_label[c])
        print("Number of paths = ",len(lengths))
        print("Shortest path length = {} ({})".format(minplen, len(spa)) )
        print("Longest path length = {} ({})".format(maxplen, len(lpa)) )
        print("Mean of path lengths = ",mean)
        print("Normalized mean = ",mean/len(lengths))
        print("Std. deviation = ",stdev)
        print("Range = ",mean-stdev, mean+stdev)
        print("Median of paths = ",median)
        print("Mode of paths = ",statistics.multimode(lengths))
        print("Dropped paths = ",dropped_paths)

        print("Normalizing Shift = ", pcalc.getshift())
        #Union of path probabilities
        list_comp = [(1-x) for x in list_prob]
        inter = numpy.prod(list_comp)
        union = 1.0 - inter
        print("P_total = ", union, " avg_pp:", statistics.mean(list_prob))

        #Metrics
        iss = 1 - ((1-CVSS_CONF)*(1-CVSS_INT)*(1-CVSS_AVAIL))
        exploitability = N1*union
        print("Exploitability = ", exploitability)
        print("Impact = (min: {}; max: {}; avg:{})".format(
            min(list_impt),
            max(list_impt),
            statistics.mean(list_impt),
        ))
        print("VRisk = (min: {}; max: {}; avg:{})".format(
            min(list_vrisk),
            max(list_vrisk),
            statistics.mean(list_vrisk)
        ))
        print("PRisk = (min: {}; max: {}; avg:{})".format(
            min(list_prisk),
            max(list_prisk),
            statistics.mean(list_prisk)
        ))
        print("Risk score   = ", sum(list_prisk))

        print("---------------modes---------------")
        if len(first) > 0:
            print("1.Mode:", [sg.vertex_label[i] for i in first ], "(",fst_val[0],")")
        if len(second) > 0:
            print("2.Mode:", [sg.vertex_label[i] for i in second ], "(",fst_val[1],")")
        if len(third) > 0:
            print("3.Mode:", [sg.vertex_label[i] for i in third ], "(",fst_val[2],")")
        if not args.no_graph:
            sg.draw(vsize=15, fsize=16, osize=[1500,1000], target=c, sources=sg.attk_nodes)

        print("-------------histogram data (bin, frequency, bin-scaled, peak-norm, path-norm)---------------")
        # plens=[ len(x) for x in ap ]
        hist,bins = numpy.histogram( lengths, bins=range(minplen, maxplen+2) )
        xscale = PNORM_BINS/(maxplen-minplen)
        yscale = PNORM_PEAK/(max(hist))
        for idx,h in enumerate(hist):
            print( bins[idx], h, (bins[idx] - minplen) * xscale, h * yscale, h/len(lengths) )
        if sum(hist) != len(lengths):
            print("HISTOGRAM NUMBER OF PATHS DIFFER FROM DETECTED PATHS:", sum(hist), len(lengths))

        print("---------------other-----------------")
        if len(mode_of_nodes_list) > 0:
            for node in mode_of_nodes_list:
                node_mode_ls = [x for x in ap if node in x]
                node_mode = len(node_mode_ls)
                nmlen = [len(i) for i in node_mode_ls]
                if node_mode > 0:
                    print("Paths via:",sg.get_nodes().get()[ sg.node_index[node] ].nname(),":",node_mode, "; median len:", statistics.median(nmlen))
                    if node_mode < 20:
                        for path in node_mode_ls:
                            print([( sg.get_nodes().get()[ sg.node_index[m] ].nname(),
                                     sg.get_nodes().get()[ sg.node_index[m] ].nprobability() )
                                   for m in path[0:] ])
                            # print([sg.vertex_label[m] for m in path])
                else:
                    print("No paths via:", sg.get_nodes().get()[ sg.node_index[node] ].nname())
                print("---------------------------------------------")

        # filter blast-radius graph
        if not args.no_graph:
            sg.blast_radius_draw( ap )

#function to calculate path probability of single path
def path_probl(path_index, vertex_probability, shift=0.0):
    prob = 1.0
    for i in path_index:
        prob = prob * vertex_probability[i]
    return prob

def tree_stats(sg, N1, N2, args):
    csall=[]
    vulnerable_nodes=[]
    protected_nodes=[]
    shift=0.0
    if not args.no_graph:
        sg.draw(vsize=15, fsize=16, osize=[1500,1000])

    for c in sg.get_targets():
        list_paths = []
        tree = min_spanning_tree(sg.g, root=c)

        #Derive tree
        u = GraphView(sg.g, efilt=tree)
        sg.vertex_fill_color[c] = (0/255.0, 0/255.0, 255.0/255.0, 1)
        # for v in sg.vuln_nodes:
        #     pr=sg.vertex_probability[v]
        #     sg.vertex_fill_color[v] = (pr, 0/255.0, 0/255.0, 1)
        # for p in sg.prot_nodes:
        #     sg.vertex_fill_color[p] = (0/255.0, 255.0/255.0, 0/255.0, 1)


        for v in sg.g.vertices():
            for path in all_paths(u,v,c):
                list_paths.append(path)
        lengths = [len(i) for i in list_paths]
        if len(list_paths) > 0:

            #Path statistics
            sg.explain_labels()
            mean = statistics.mean(lengths)
            stdev = statistics.stdev(lengths)
            median = statistics.median(lengths)
            print("=============================================================")
            print("Critical node = ",sg.vertex_label[c])
            print("Number of paths = ",len(lengths))
            print("Shortest path length = ",min(lengths))
            print("Mean of path lengths = ",mean)
            print("Normalized mean = ",mean/len(lengths))
            print("Std. deviation = ",stdev)
            print("Range = ",mean-stdev, mean+stdev)
            print("Median of paths = ",median)
            print("Mode of paths = ",statistics.mode(lengths))

            #path probabilities of all paths
            list_prob=[]
            for v in sg.g.vertices():
                for path in all_paths(u,v,c):
                    list_prob.append(path_probl(path,sg.vertex_probability, shift=shift))

            #Union of path probabilities
            list_comp = [1-x for x in list_prob]
            inter = numpy.prod(list_comp)
            union = 1.0 - inter
            print("P_total = ", union)

            #Metrics
            iss = 1 - ((1-CVSS_CONF)*(1-CVSS_INT)*(1-CVSS_AVAIL))
            exploitability = N1*union
            impact = N2*iss
            print("Exploitability = ", exploitability)
            print("Impact = (NOT YET UPDATED TO NEW VERSION)",impact)
            print("Base score = ", exploitability+impact)
            csall.append(exploitability+impact)

            print("CSV:", sg.vertex_label[c], len(lengths), min(lengths), mean, mean/len(lengths),
              stdev, median, union, exploitability, impact, exploitability+impact )

        # draw the graph after the stats-print to see graph and stats side-by-side
        deg = prop_to_size(sg.g.vertex_properties["vertex_probability"], mi=20, ma=60)
        if not args.no_graph:
            graph_draw(u,
                   vertex_size=deg,
                   vertex_text=sg.vertex_label,
                   vertex_font_size=14,
                   vertex_fill_color=sg.g.vertex_properties['vertex_fill_color'],
                   vertex_pen_width=0.0,
                   vertex_text_out_width=0.0,
                   vertex_text_position=5.0,
                   vertex_text_offset=[-0.01,0.005],
                   edge_pen_width=3,
                   edge_color=(180/255.0,180/255.0,180/255.0, 1),
                   output_size=[1500,1000])
        # graph_draw(u,
        #            vertex_size=15,
        #            vertex_text=sg.vertex_label,
        #            vertex_font_size=14,
        #            vertex_fill_color=sg.g.vertex_properties['vertex_fill_color'],
        #            output_size=[1500,1000])
        # reset color for next critical node:
        sg.vertex_fill_color[c] = (sg.vertex_probability[c], 0/255.0, 0/255.0, 1)

    if len(csall)>0:
        print("Total Base score mean = ", statistics.mean(csall))


def main():

    args = tools.cmdline()
    config = tools.StrongConfig(args)

    global MAX_PATHS
    MAX_PATHS=args.max_path
    global DEFAULT_PROBABILITY
    DEFAULT_PROBABILITY=abs(args.default_prob)
    global STRUCTURAL_SHIFT
    STRUCTURAL_SHIFT=args.structure_shift


    ymldata = tools.load_files(args.input_file)
    gr = sgr.StrongGraph(ymldata, config)
    # gr.collapse_stencils()
    print([ (g.gname(),g.gprobability()) for _,g in gr.groups.get().items() ])
#    return -1

    sg = sec_graph(gr)

    sg.generate_graph(args.unidir)

    if args.output == "pgt":
        if args.antype.lower() == "path":
            path_stats(sg, N1, N2, args)
        else:
            tree_stats(sg, N1, N2, args)
    return 0
# elif args.output == "yml":
#     gdata.export_combined_yml(args.file)
# else:
#     print("Error: unrecognized/unimplemented export option. -o <pgt|yml>")
#     return -1

main()

# System Topology Risk analysis on Graphs (STRonG)

## Graph Specification

Graph input is handled via yaml files. An example can be found in `examples/test/testcase.yml`.
A specification pdf is part of this repo.

## Tool Prereqs

 * The tool uses the /graph-tool/ library
   (https://graph-tool.skewed.de/). Which might not come with your
   default python package mgr. Please see the website for different
   options of installation (container, conda-forge, source, ...)

 * Also, the `pyyaml` Python package is needed.

 * Code uses Python 3 syntax with no plans to backport to Python 2 ;-).


## Running the tool

The main python script is `strong.py`. It will print a help message
explaining the available parameters when running `python strong.py -h`.

To run an example test case and produce and process a simple graph that already
includes a number of features like stencils and scoring groups:
```
 python strong.py examples/test/testcase.yml
```

NOTE: Large graphs can require large amounts of memory. This is something to improve
in the future.


## Reading the output

The tool will open a window (unless option `-g` is used) and show the graph. It
attempts to arrange the nodes, but usually fails to show the layering.  You can grab
and move the nodes around to organise the picture for a screenshot.

The first window that opens contains the graph as specified. Once that window is closed,
the tool generates the conjugated graph and opens a new window displaying this graph.  Using
the conjugated graph is an experimental way to allow handling the traversal of the original graph
and allow multiple visits to the same vertex without getting stuck in loops (use the `-e` option
for stats on the conjugated graph).

The amount of stdout output is substantial, however, the important sections are at the bottom.
Depending on the level of detail you look for, the output of interest might start after:
```
Detecting paths...
calculating path probabilities...
```

Followed by sections containing the list of shortest paths, paths in
general, and longest paths.  The node names in these path lists will
contain the shortened node names plus their node score. The type of
name shortening is explained after the list of paths is printed in a
line starting with `Shortening uses ...`, for example:

```
Shortening uses the first 3 chars and then adds the 1st char from the end of the substring.
```

The main statistics output follows after a line of `====`.
```
=============================================================
Critical node =  sers_rabq_core.0.1013
Number of paths =  4584
Shortest path length = 5 (1)
Longest path length = 19 (32)
Mean of path lengths =  14.462478184991275
Normalized mean =  0.0031549908780521977
Std. deviation =  2.1095641773852725
Range =  12.352914007606003 16.572042362376546
Median of paths =  15.0
Mode of paths =  [15]
Dropped paths =  0
Normalizing Shift =  -0.0118408203125
P_total =  0.0030686767364933587  avg_pp: 6.703271999670881e-07
Exploitability =  0.011845092202864364
Impact = (min: 22.25309563648847; max: 95.62039299529577; avg:73.0154458823329)
VRisk = (min: 0.630939358977449; max: 1.8734052059461341; avg:1.132972259928185)
PRisk = (min: 8.525729180947748e-14; max: 0.017625612102005094; avg:1.898743145769437e-05)
Risk score   =  0.08703838580207088
```

The main section is followed by the list of the nodes with the highest
to third-highest modes.  In the example you see node
`oss_conS_grod.0.2326` listed as a first-mode vertex being part of 496
paths. This also tells you, there's no other node being part of more
than 496 paths. Note that there can be multiple vertices within the
same mode.
```
---------------modes---------------
1.Mode: ['oss_comS_grod.0.2326'] ( 496 )
2.Mode: ['oss_fwOS_grod.0.2326'] ( 464 )
3.Mode: ['oss_conS_grod.0.2326'] ( 458 )
```


The next section of output is the path length histogram. The first 2
columns are the absolute values of the bin and the frequency.  The
last 3 columns are normalized/scaled forms of the histogram. The
scaled bin is created by mapping the initial bins onto a range of
0..100. The peak-norm is a normalization of the frequency such that
the peak is at 1000. The path-norm is a normalization of the frequency
such that the frequency is divided by the total number of paths.

```
-------------histogram data (bin, frequency, bin-scaled, peak-norm, path-norm)---------------
5 1 0.0 7.8125 0.0018115942028985507
6 5 10.0 39.0625 0.009057971014492754
7 8 20.0 62.5 0.014492753623188406
8 24 30.0 187.5 0.043478260869565216
9 30 40.0 234.375 0.05434782608695652
10 36 50.0 281.25 0.06521739130434782
11 79 60.0 617.1875 0.1431159420289855
12 91 70.0 710.9375 0.16485507246376813
13 128 80.0 1000.0 0.2318840579710145
14 82 90.0 640.625 0.14855072463768115
15 68 100.0 531.25 0.12318840579710146
```


The last section will be populated if the user requests the list of
paths for particular nodes (using the `-M ...` argument).  Warning:
this feature is not scalably implemented yet. So if your requested
node is part of millions of paths in a large graph, the tool will
attempt to print all of them. Node names will be printed as there full
names and paired with their score.

```
---------------other-----------------
Paths via: services.protocheck.core : 8 ; median len: 10.0
[('user.attksrc', 1), ('iso.memiso', 0.296), ... ]
[('user.attksrc', 1), ('iso.memiso', 0.296), ... ]
[('user.attksrc', 1), ('iso.memiso', 0.296), ... ]
...

```

Note: If multiple target/critical nodes are defined, the output will
be created for each of the targets separately.

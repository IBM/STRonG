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

class StrongGroup:
    def __init__(self, name, prob, prio):
        self.name = name
        self.probability = prob
        self.priority = prio

    def gname(self):
        return self.name

    def gprobability(self):
        return self.probability

    def gpriority(self):
        return self.priority

    def setprob(self, prob):
        self.probability = prob

class StrongGroups:
    # the order of the groups is important for priority
    def __init__(self, ymldata, ovrrd):
        self.groups = {}
        print("GROUPDATA:", ymldata, ovrrd)
        ovrrd_offset=len(ovrrd)
        for prio,g in enumerate(ymldata):
            for k,v in g.items():
                if k in ovrrd:
                    print("Groupprob override:", k, ovrrd[k])
                    self.add(k, ovrrd[k][0], prio+ovrrd_offset) # cmdline override
                else:
                    self.add(k, v, prio+ovrrd_offset) # regular yml defined

        # add groups not defined in yml but on cmd line (at higher priority)
        for a,b in ovrrd.items():
            if a not in self.groups:
                self.add( a, b[0], b[1])
        self.log()

    def add(self, name, prob, prio):
        if name not in self.groups:
            self.groups[name] = StrongGroup(name, prob, prio)
        return self.groups[name]

    def get(self):
        return self.groups

    def find(self, name):
        if name in self.groups:
            return self.groups[name]
        else:
            return None

    def log(self):
        for k,v in self.groups.items():
            print(k, ":", v.gprobability(), ",", v.gpriority())

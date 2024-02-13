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

class Layer:
    def __init__(self, name, upper = "none", lower = "none", data={}):
        LAYER_DEFAULTS={"upper":"none",
                        "lower":"none"}

        # todo: lowercase for all layer name references

        self.name = name.lower()
        for key,default in LAYER_DEFAULTS.items():
            if key not in data:
                setattr(self, key, locals()[key].lower())
            else:
                setattr(self, key, data[key].lower())

        # print( self.lname(), self.lupper(), self.llower())


    def lname(self):
        return self.name
    def lupper(self):
        return self.upper
    def llower(self):
        return self.lower


# layers mostly addressed by name, so make it dictionary
# ordered layers are list for ordered top-down iteration
class LayerList:
    def __init__(self):
        self.layers = {}
        self.sorted = []

    def get(self):
        return self.layers
    def ordered(self):
        return self.sorted
    def find(self, name):
        if name in self.layers:
            return self.layers[name]
        else:
            return None

    def add(self, name, ldata):
        if name in self.layers:
            print("WARNING: trying to add a stencil that already exits.")
        else:
            print("LAYER: adding new: ",name)
            self.layers[name] = Layer(name, data=ldata)
            self.sorted = self.order()
        return self.layers[name]


    # todo: this is extremely poor/primitive/stupid way of sorting need to look into proper comparator-based way for python3
    def order(self):
        ordered=[]
        current="none"
        for n,s in self.layers.items():
            for _,l in self.layers.items():
                if l.lupper() == current:
                    ordered.append(l)
                    current = l.lname()
                    break

        return ordered


    def log(self):
        print("Layers :", [ {l.lname(): [l.lupper(), l.llower()]} for _,l in self.get().items() ] )
        print("Ordered:", [ {l.lname(): [l.lupper(), l.llower()]} for l in self.ordered() ] )

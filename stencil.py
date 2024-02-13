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


class Stencil:
    def __init__(self, sname, sdata):
        self.name = sname
        self.data = sdata.copy()
        self.data.pop("type",[]) # type info can be removed, at this point we know what we are
        return

    def sname(self):
        return self.name
    def sdata(self):
        return self.data

# stencils should be addressable by name, so this will be a dictionary
class StencilList:
    def __init__(self):
        self.stencils={}

        # print(stencilfile, " is located in directory:", os.path.dirname(stencilfile) )
        # with open(stencilfile, 'r') as data_stream:
        #     stencildata = yaml.load(data_stream, Loader=yaml.Loader)

        #     for name,sdata in stencildata.items():
        #         if "type" in sdata and sdata["type"].lower() == "stencil":
        #             self.layers[name] = Layer(name, data = ldata)

    def add(self, name, sdata):
        if name in self.stencils:
            print("WARNING: trying to add a stencil that already exits.")
        else:
            self.stencils[name] = Stencil( name, sdata )
        return self.stencils[name]

    def get(self):
        return self.stencils

# Soprano - a library to crack crystals! by Simone Sturniolo
# Copyright (C) 2016 - Science and Technology Facility Council

# Soprano is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Soprano is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Definition of AtomsProperty class.

A generic template class that specific Properties will inherit from.
"""


from soprano.collection import AtomsCollection


class AtomsProperty:

    default_name = "generic_property"
    default_params = {}

    def __init__(self, name=None, **params):
        """Initialize an AtomsProperty and set its parameters.
        The AtomsProperty instance can then be called with a structure as its
        only argument to get the property with the given parameters.

        | Args:
        |   name (str): a name to give to this specific instance of the
        |               property (will be used to store it as array if
        |               requested)
        |   params: named arguments specific to this type of property

        """

        if name is not None:
            self.name = name
        else:
            self.name = self.default_name
        # Validate the passed parameters
        self.params = dict(self.default_params)
        for p in params:
            if p not in self.params:
                raise ValueError(
                    "Invalid argument passed to"
                    f" '{self.__class__.__name__}'"
                )
            else:
                self.params[p] = params[p]

    @classmethod
    def get(self, s, store_array=False, average=False,**kwargs):
        """Extract the given property using the default parameters
        on an Atoms object s

        | Args:
        |   s (ase.Atoms or AtomsCollection): the structure or collection
        |                                     from which to extract the
        |                                     property
        |   store_array (bool): if s is a collection, whether to store the
        |                       resulting data as an array in the collection
        |                       using the default name for this property
        |   average (bool): if s is a trajectory (list of Atoms), whether to return
        |                   the average property across all frames. Default is False.
        |

        | Returns:
        |   property: the value of the property for the given structure or
        |             a list of values if a collection has been passed
        |

        """

        if isinstance(s, AtomsCollection):
            arr = s.all.map(self.get, **kwargs)
            if store_array:
                s.set_array(self.default_name, arr)
            return arr
        elif isinstance(s, list):
            if average == True:
                results = [self.get(a, **kwargs) for a in s]

                if results and isinstance(results[0], list) and len(results[0]) > 0:
                    from soprano.nmr.tensor import NMRTensor

                    if hasattr(results[0][0], 'data'):
                        n_atoms = min(len(r) for r in results)
                        return [NMRTensor.average([r[i] for r in results]) for i in range(n_atoms)]
                
                return sum(results) / len(results) if results else None

            else:
                # Select the last frame by default if average is False
                return self.get(s[-1], **kwargs)
        else:
            params = dict(self.default_params)
            params.update(kwargs)
            return self.extract(s, **params)

    @staticmethod
    def extract(s, **params):
        """Extract the given property with given parameters from an Atoms
        object.

        | Args:
        |   s (ase.Atoms): the structure from which to extract the property
        |   params: named arguments specific to this type of property
        |

        | Returns:
        |   property: the value of the property for the given structure and
        |             parameters
        |

        """

        # Do something specific to get the property of interest
        # Then return the value


    def __call__(self, s, store_array=False):
        """Calling the AtomsProperty returns the value of the property as
        extracted with the parameters of this specific instance.

        | Args:
        |   s (ase.Atoms or AtomsCollection): the structure or collection
        |                                     from which to extract the
        |                                     property
        |   store_array (bool): if s is a collection, whether to store the
        |                       resulting data as an array in the collection
        |                       using the given name for this instance
        |

        | Returns:
        |   property: the value of the property for the given structure or
        |             a list of values if a collection has been passed
        |

        """

        if isinstance(s, AtomsCollection):
            arr = s.all.map(self.__call__)
            if store_array:
                s.set_array(self.name, arr)
            return arr
        else:
            return self.extract(s, **self.params)

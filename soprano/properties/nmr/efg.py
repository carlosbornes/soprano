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

"""Implementation of AtomsProperties that relate to NMR electric field
gradients"""

from collections import defaultdict
from typing import List

import numpy as np

from soprano.data.nmr import EFG_TO_CHI, _get_isotope_data, _get_isotope_list
from soprano.nmr import ElectricFieldGradient
from soprano.nmr.utils import (
    _anisotropy,
    _asymmetry,
    _frange,
    _haeb_sort,
    _skew,
    _span,
)
from soprano.properties import AtomsProperty


def _has_efg_check(f):
    # Decorator to add a check for the electric field gradient array
    def decorated_f(s, *args, **kwargs):
        if not (s.has("efg")):
            raise RuntimeError(
                "No electric field gradient data found for" " this system"
            )
        return f(s, *args, **kwargs)

    return decorated_f


class EFGTensor(AtomsProperty):
    """
    EFGTensor

    Produces a list of ElectricFieldGradient objects containing the electric field
    gradient tensors for each atom in the system.
    Requires the Atoms object to have
    been loaded from a .magres file containing the relevant information.

    The default convention for EFG tensors is the NQR one (`|Vxx| ≤ |Vyy| ≤ |Vzz|`).
    This is different from the default convention for MS tensors (Haeberlen).
    You can change this by specifying the 'order' parameter.

    Parameters:
        order (str):  Order to use for eigenvalues/eigenvectors. Can
                    be 'i' (ORDER_INCREASING), 'd'
                    (ORDER_DECREASING), 'h' (ORDER_HAEBERLEN) or
                    'n' (ORDER_NQR). Default is 'n'.
        use_q_isotopes (bool): if True, always use the most common quadrupole
                             active isotope for each element, if there is
                             one.
        isotopes (dict): dictionary of specific isotopes to use, by element
                         symbol. If the isotope doesn't exist an error will
                          be raised. Overrides use_q_isotopes.
        isotope_list (list): list of isotopes, atom-by-atom. To be used if
                           different atoms of the same element are supposed
                           to be of different isotopes. Where a 'None' is
                           present will fall back on the previous
                           definitions. Where an isotope is present it
                           overrides everything else.

    Returns:
      efg_tensors (list): list of ElectricFieldGradient objects

    """

    default_name = "efg_tensors"
    default_params = {
        "order": ElectricFieldGradient.ORDER_NQR,
        "use_q_isotopes": False,
        "isotopes": {},
        "isotope_list": None,
                      }

    @staticmethod
    @_has_efg_check
    def extract(s, order, use_q_isotopes, isotopes, isotope_list) -> List[ElectricFieldGradient]:

        # First thing, build the isotope dictionary
        elems = s.get_chemical_symbols()

        # Is isotope list valid?
        if isotope_list is not None and len(isotope_list) != len(elems):
            print("WARNING - invalid isotope_list, ignoring")
            isotope_list = None

        # Get the isotope list given the parameters
        isotopelist = _get_isotope_list(elems, isotopes=isotopes, isotope_list=isotope_list, use_q_isotopes=use_q_isotopes)
        # convert list of numbers to isotope symbols
        isotopelist = [f"{iso}{elem}" for iso, elem in zip(isotopelist, elems)]

        efg_tensors = [ElectricFieldGradient(efg, species, order=order) for efg, species in zip(s.get_array("efg"), isotopelist)]
        return efg_tensors





class EFGDiagonal(AtomsProperty):

    """
    EFGDiagonal

    Produces an array containing eigenvalues and eigenvectors for the
    symmetric part of each EFG tensor in the system. By default
    saves them as part of the Atoms' arrays as well.
    Requires the Atoms object to have been loaded from a .magres file
    containing the relevant information.

    Parameters:
      save_array (bool): if True, save the diagonalised tensors in the
                         Atoms object as an array. By default True.

    Returns:
      efg_diag (np.ndarray): list of eigenvalues and eigenvectors

    """

    default_name = "efg_diagonal"
    default_params = {"save_array": True}

    @staticmethod
    @_has_efg_check
    def extract(s, save_array):

        efg_diag = [np.linalg.eigh((efg + efg.T) / 2.0) for efg in s.get_array("efg")]
        efg_evals, efg_evecs = (np.array(a) for a in zip(*efg_diag))

        if save_array:
            s.set_array(EFGDiagonal.default_name + "_evals", efg_evals)
            # Store also the Haeberlen sorted version
            s.set_array(
                EFGDiagonal.default_name + "_evals_hsort", _haeb_sort(efg_evals)
            )
            s.set_array(EFGDiagonal.default_name + "_evecs", efg_evecs)

        return np.array([dict(zip(("evals", "evecs"), efg)) for efg in efg_diag])


class EFGVzz(AtomsProperty):

    """
    EFGVzz

    Produces an array containing the major component of the electric field
    gradient in a system (au).
    Requires the Atoms object to have been loaded from a .magres file
    containing the relevant information.

    Parameters:
      force_recalc (bool): if True, always diagonalise the tensors even if
                           already present.

    Returns:
      efg_list (np.ndarray): list of Vzz values
    """

    default_name = "efg_vzz"
    default_params = {"force_recalc": False}

    @staticmethod
    @_has_efg_check
    def extract(s, force_recalc):

        if not s.has(EFGDiagonal.default_name + "_evals_hsort") or force_recalc:
            EFGDiagonal.get(s)

        efg_evals = s.get_array(EFGDiagonal.default_name + "_evals_hsort")

        return efg_evals[:, -1]


class EFGAnisotropy(AtomsProperty):

    """
    EFGAnisotropy

    Produces an array containing the electric field gradient anisotropies in a
    system (au).
    Requires the Atoms object to have been loaded from a .magres file
    containing the relevant information.

    Parameters:
      force_recalc (bool): if True, always diagonalise the tensors even if
                           already present.

    Returns:
      efg_list (np.ndarray): list of anisotropies

    """

    default_name = "efg_anisotropy"
    default_params = {"force_recalc": False}

    @staticmethod
    @_has_efg_check
    def extract(s, force_recalc):

        if not s.has(EFGDiagonal.default_name + "_evals_hsort") or force_recalc:
            EFGDiagonal.get(s)

        efg_evals = s.get_array(EFGDiagonal.default_name + "_evals_hsort")

        return _anisotropy(efg_evals)


class EFGReducedAnisotropy(AtomsProperty):

    """
    EFGReducedAnisotropy

    Produces an array containing the electric field gradient reduced
    anisotropies in a system (au).
    Requires the Atoms object to have been loaded from a .magres file
    containing the relevant information.

    Parameters:
      force_recalc (bool): if True, always diagonalise the tensors even if
                           already present.

    Returns:
      efg_list (np.ndarray): list of reduced anisotropies

    """

    default_name = "efg_red_anisotropy"
    default_params = {"force_recalc": False}

    @staticmethod
    @_has_efg_check
    def extract(s, force_recalc):

        if not s.has(EFGDiagonal.default_name + "_evals_hsort") or force_recalc:
            EFGDiagonal.get(s)

        efg_evals = s.get_array(EFGDiagonal.default_name + "_evals_hsort")

        return _anisotropy(efg_evals, reduced=True)


class EFGAsymmetry(AtomsProperty):

    """
    EFGAsymmetry

    Produces an array containing the electric field gradient asymmetries
    in a system (adimensional).
    Requires the Atoms object to have been loaded from a .magres file
    containing the relevant information.

    Parameters:
      force_recalc (bool): if True, always diagonalise the tensors even if
                           already present.

    Returns:
      efg_list (np.ndarray): list of asymmetries

    """

    default_name = "efg_asymmetry"
    default_params = {"force_recalc": False}

    @staticmethod
    @_has_efg_check
    def extract(s, force_recalc):

        if not s.has(EFGDiagonal.default_name + "_evals_hsort") or force_recalc:
            EFGDiagonal.get(s)

        efg_evals = s.get_array(EFGDiagonal.default_name + "_evals_hsort")

        return _asymmetry(efg_evals)


class EFGSpan(AtomsProperty):

    """
    EFGSpan

    Produces an array containing the electric field gradient tensor span
    in a system (au).
    Requires the Atoms object to have been loaded from a .magres file
    containing the relevant information.

    Parameters:
      force_recalc (bool): if True, always diagonalise the tensors even if
                           already present.

    Returns:
      efg_list (np.ndarray): list of spans

    """

    default_name = "efg_span"
    default_params = {"force_recalc": False}

    @staticmethod
    @_has_efg_check
    def extract(s, force_recalc):

        if not s.has(EFGDiagonal.default_name + "_evals_hsort") or force_recalc:
            EFGDiagonal.get(s)

        efg_evals = s.get_array(EFGDiagonal.default_name + "_evals_hsort")

        return _span(efg_evals)


class EFGSkew(AtomsProperty):

    """
    EFGSkew

    Produces an array containing the electric field gradient tensor skew
    in a system.
    Requires the Atoms object to have been loaded from a .magres file
    containing the relevant information.

    Parameters:
      force_recalc (bool): if True, always diagonalise the tensors even if
                           already present.

    Returns:
      efg_list (np.ndarray): list of skews

    """

    default_name = "efg_skew"
    default_params = {"force_recalc": False}

    @staticmethod
    @_has_efg_check
    def extract(s, force_recalc):

        if not s.has(EFGDiagonal.default_name + "_evals_hsort") or force_recalc:
            EFGDiagonal.get(s)

        efg_evals = s.get_array(EFGDiagonal.default_name + "_evals_hsort")

        return _skew(efg_evals)


class EFGQuadrupolarConstant(AtomsProperty):

    """
    EFGQuadrupolarConstant

    Produces an array containing the quadrupolar constant in Hz for every atom
    in a system. The constant will be zero for non-quadrupole active nuclei.
    Unless specified otherwise, the quadrupole moment of the most common
    NMR-active isotope is used.
    For reference: the value returned by this property is defined as

    .. math::

        \\frac{e^2qQ}{h}

    in Hz. It is important to keep in mind that therefore this represents a
    *frequency*; the corresponding 'omega' (pulsation) would be the same value
    multiplied by 2*pi. This is, for example, exactly the value required as
    input in Simpson's SPINSYS section.

    Parameters:
      force_recalc (bool): if True, always diagonalise the tensors even if
                           already present.
      use_q_isotopes (bool): if True, always use the most common quadrupole
                             active isotope for each element, if there is
                             one.
      isotopes (dict): dictionary of specific isotopes to use, by element
                       symbol. If the isotope doesn't exist an error will
                       be raised. Overrides use_q_isotopes.
      isotope_list (list): list of isotopes, atom-by-atom. To be used if
                           different atoms of the same element are supposed
                           to be of different isotopes. Where a 'None' is
                           present will fall back on the previous
                           definitions. Where an isotope is present it
                           overrides everything else.

    Returns:
      q_list (np.ndarray): list of quadrupole constants in Hz

    """

    default_name = "efg_qconst"
    default_params = {
        "force_recalc": False,
        "use_q_isotopes": False,
        "isotopes": {},
        "isotope_list": None,
    }

    @staticmethod
    @_has_efg_check
    def extract(s, force_recalc, use_q_isotopes, isotopes, isotope_list):

        if not s.has(EFGDiagonal.default_name + "_evals_hsort") or force_recalc:
            EFGDiagonal.get(s)

        # First thing, build the isotope dictionary
        elems = s.get_chemical_symbols()

        # Is isotope list valid?
        if isotope_list is not None and len(isotope_list) != len(elems):
            print("WARNING - invalid isotope_list, ignoring")
            isotope_list = None

        q_list = _get_isotope_data(elems, "Q", isotopes, isotope_list, use_q_isotopes)

        return EFG_TO_CHI * q_list * EFGVzz.get(s)
class EFGNQR(AtomsProperty):

    """
    EFGNQR

    Produces an array containing NQR transition frequencies (in Hz) for every atom
    in a system. For non-quadrupole active nuclei, the we return an empty dictionary.
    Unless specified otherwise, the spin and quadrupole moment of the most common
    NMR-active isotope is used.

    For reference: the value returned by this property is defined as

    .. math::

        A = \\frac{V_{zz} Q}{4I(2I - 1)}
        fq = 3A(2m+1)\\sqrt{1 + \\eta^2/3}

    in Hz.
    It is important to keep in mind that therefore this represents a
    *frequency*; the corresponding 'omega' (pulsation) would be the same value
    multiplied by 2*pi. 
    TODO: double-check convention
    TODO: better data structure for the output?

    Parameters:
      force_recalc (bool): if True, always diagonalise the tensors even if
                           already present.
      use_q_isotopes (bool): if True, always use the most common quadrupole
                             active isotope for each element, if there is
                             one.
      isotopes (dict): dictionary of specific isotopes to use, by element
                       symbol. If the isotope doesn't exist an error will
                       be raised. Overrides use_q_isotopes.
      isotope_list (list): list of isotopes, atom-by-atom. To be used if
                           different atoms of the same element are supposed
                           to be of different isotopes. Where a 'None' is
                           present will fall back on the previous
                           definitions. Where an isotope is present it
                           overrides everything else.

    Returns:
      q_list (list): list of dictionaries of the possible NQR frequencies in Hz
                        The keys of the dictionary are the possible m->m+1 values
                        For example: "m=1->2" for non-quadrupole active nuclei
                        the corresponding element will be an empty dictionary.

    """

    default_name = "efg_nqr"
    default_params = {
        "force_recalc": False,
        "use_q_isotopes": False,
        "isotopes": {},
        "isotope_list": None,
    }

    @staticmethod
    @_has_efg_check
    def extract(s, force_recalc, use_q_isotopes, isotopes, isotope_list):

        if not s.has(EFGDiagonal.default_name + "_evals_hsort") or force_recalc:
            EFGDiagonal.get(s)

        # First thing, build the isotope dictionary
        elems = s.get_chemical_symbols()

        # Is isotope list valid?
        if isotope_list is not None and len(isotope_list) != len(elems):
            print("WARNING - invalid isotope_list, ignoring")
            isotope_list = None

        q_list = _get_isotope_data(elems, "Q", isotopes, isotope_list, use_q_isotopes)
        I_list = _get_isotope_data(elems, "I", isotopes, isotope_list, use_q_isotopes)
        eta_list = EFGAsymmetry.get(s)
        nqr = [defaultdict(None) for i in range(len(elems))]

        mask = I_list > 0.5
        for i in np.where(mask)[0]:
            A = EFG_TO_CHI * EFGVzz.get(s)[i] * q_list[i] / (4 * I_list[i] * (2 * I_list[i] - 1))
            ms = [m for m in _frange(-I_list[i], I_list[i] + 1, 1) if m >= 0.0][:-1]
            for m in ms:
                key = f'm={m}->{m+1}'
                fq = 3 * A * (2 * m + 1) * np.sqrt(1 + eta_list[i] ** 2 / 3)
                nqr[i][key] = fq


        return nqr

class EFGQuadrupolarProduct(AtomsProperty):

    """
    EFGQuadrupolarProduct

    Produces an array containing the quadrupolar product values
    in a system.
    Requires the Atoms object to have been loaded from a .magres file
    containing the relevant information.

    .. math::

        \\P_Q = C_Q (1+frac{\\eta_Q^2}{3})^{1/2}

    Parameters:
      force_recalc (bool): if True, always diagonalise the tensors even if
                           already present.
      use_q_isotopes (bool): if True, always use the most common quadrupole
                             active isotope for each element, if there is
                             one.
      isotopes (dict): dictionary of specific isotopes to use, by element
                       symbol. If the isotope doesn't exist an error will
                       be raised. Overrides use_q_isotopes.
      isotope_list (list): list of isotopes, atom-by-atom. To be used if
                           different atoms of the same element are supposed
                           to be of different isotopes. Where a 'None' is
                           present will fall back on the previous
                           definitions. Where an isotope is present it
                           overrides everything else.

    Returns:
      Pq_list (np.ndarray): list of quadrupole products in Hz (units of Cq)

    """

    default_name = "efg_qprod"
    default_params = {
        "force_recalc": False,
        "use_q_isotopes": False,
        "isotopes": {},
        "isotope_list": None,
    }

    @staticmethod
    @_has_efg_check
    def extract(s, force_recalc, use_q_isotopes, isotopes, isotope_list):

        if not s.has(EFGDiagonal.default_name + "_evals_hsort") or force_recalc:
            EFGDiagonal.get(s)

        # First thing, build the isotope dictionary
        elems = s.get_chemical_symbols()

        # Is isotope list valid?
        if isotope_list is not None and len(isotope_list) != len(elems):
            print("WARNING - invalid isotope_list, ignoring")
            isotope_list = None

        q_list = _get_isotope_data(elems, "Q", isotopes, isotope_list, use_q_isotopes)

        return (
            EFG_TO_CHI
            * q_list
            * EFGVzz.get(s)
            * (1 + (EFGAsymmetry.get(s) ** 2) / 3) ** 0.5
        )

class EFGEuler(AtomsProperty):

    """
    EFGEuler

    Produces an array of Euler angles in radians expressing the orientation of
    the EFG tensors with respect to the cartesian axes for each site in the Atoms object.
    Requires the Atoms object to have been loaded from a .magres file
    containing the relevant information.


    Parameters:
        order (str):  Order to use for eigenvalues/eigenvectors. Can
                        be 'i' (ORDER_INCREASING), 'd'
                        (ORDER_DECREASING), 'h' (ORDER_HAEBERLEN) or
                        'n' (ORDER_NQR). Default is 'n' for EFG tensors.
        convention (str): 'zyz' or 'zxz' accepted - the ordering of the Euler
                        angle rotation axes. Default is ZYZ 
        passive (bool):  active or passive rotations. Default is active (passive=False)
         

    Returns:
        efg_eulers (np.array): array of Euler angles in radians

    """

    default_name = "efg_eulers"
    default_params = {"order": ElectricFieldGradient.ORDER_NQR,
                      "convention": "zyz",
                      "passive": False}

    @staticmethod
    @_has_efg_check
    def extract(s, order, convention, passive):
        return np.array([t.euler_angles(convention, passive=passive) for t in EFGTensor.get(s, order=order)])



class EFGQuaternion(AtomsProperty):

    """
    EFGQuaternion

    Produces a list of ase.Quaternion objects expressing the orientation of
    the EFG tensors with respect to the cartesian axes.
    Requires the Atoms object to have been loaded from a .magres file
    containing the relevant information.

    The default convention for EFG tensors is the NQR one (`|Vxx| ≤ |Vyy| ≤ |Vzz|`).
    This is different from the default convention for MS tensors (Haeberlen).
    You can change this by specifying the 'order' parameter.

    Parameters:
      order (str):  Order to use for eigenvalues/eigenvectors. Can
                    be 'i' (ORDER_INCREASING), 'd'
                    (ORDER_DECREASING), 'h' (ORDER_HAEBERLEN) or
                    'n' (ORDER_NQR). Default is 'n'.

    Returns:
      efg_quat (list): list of quaternions

    """

    default_name = "efg_quats"
    default_params = {"order": ElectricFieldGradient.ORDER_NQR}

    @staticmethod
    @_has_efg_check
    def extract(s, order):
        return [t.quaternion for t in EFGTensor.get(s, order=order)]

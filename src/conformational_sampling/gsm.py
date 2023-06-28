from pathlib import Path
import sys
import pyGSM
# workaround for issue with pyGSM installation
sys.path.append(str(Path(pyGSM.__file__).parent))
import ase.io
import numpy as np
from ase.calculators.morse import MorsePotential

from pyGSM.coordinate_systems import DelocalizedInternalCoordinates, PrimitiveInternalCoordinates, Distance, Topology
from pyGSM.level_of_theories.ase import ASELoT
from pyGSM.optimizers import eigenvector_follow
from pyGSM.potential_energy_surfaces import PES
from pyGSM.utilities import elements, manage_xyz, nifty
from pyGSM.molecule import Molecule
from pyGSM.growing_string_methods import SE_GSM
from pyGSM.utilities.cli_utils import plot as gsm_plot
from pyGSM.utilities.cli_utils import get_driving_coord_prim
import stk

from conformational_sampling.config import Config

def stk_gsm(stk_mol: stk.Molecule, driving_coordinates, config: Config):
    nifty.printcool(" Building the LOT")
    ELEMENT_TABLE = elements.ElementData()
    atoms = [ELEMENT_TABLE.from_atomic_number(atom.get_atomic_number())
             for atom in stk_mol.get_atoms()]
    xyz = stk_mol.get_position_matrix()
    atom_symbols = np.array(list(atom.symbol for atom in atoms))
    
    # geom is an aggregate ndarray with the structure of the body of an XYZ file
    geom = np.column_stack([atom_symbols, xyz]).tolist()
    lot = ASELoT.from_options(config.ase_calculator, geom=geom)

    nifty.printcool(" Building the PES")
    pes = PES.from_options(
        lot=lot,
        ad_idx=0,
        multiplicity=1,
    )

    nifty.printcool("Building the topology")
    top = Topology.build_topology(
        xyz,
        atoms,
    )

    driving_coord_prims = []
    for dc in driving_coordinates:
        prim = get_driving_coord_prim(dc)
        if prim is not None:
            driving_coord_prims.append(prim)

    for prim in driving_coord_prims:
        if type(prim) == Distance:
            bond = (prim.atoms[0], prim.atoms[1])
            if bond in top.edges:
                pass
            elif (bond[1], bond[0]) in top.edges():
                pass
            else:
                print(" Adding bond {} to top1".format(bond))
                top.add_edge(bond[0], bond[1])

    nifty.printcool("Building Primitive Internal Coordinates")
    p1 = PrimitiveInternalCoordinates.from_options(
        xyz=xyz,
        atoms=atoms,
        addtr=False,  # Add TRIC
        topology=top,
    )

    nifty.printcool("Building Delocalized Internal Coordinates")
    coord_obj1 = DelocalizedInternalCoordinates.from_options(
        xyz=xyz,
        atoms=atoms,
        addtr=False,  # Add TRIC
        primitives=p1,
    )

    nifty.printcool("Building Molecule")
    reactant = Molecule.from_options(
        geom=geom,
        PES=pes,
        coord_obj=coord_obj1,
        Form_Hessian=True,
    )

    nifty.printcool("Creating optimizer")
    optimizer = eigenvector_follow.from_options(Linesearch='backtrack', OPTTHRESH=0.005, DMAX=0.5, abs_max_step=0.5,
                                                conv_Ediff=0.5)

    nifty.printcool("initial energy is {:5.4f} kcal/mol".format(reactant.energy))

    se_gsm = SE_GSM.from_options(
        reactant=reactant,
        nnodes=7,
        optimizer=optimizer,
        xyz_writer=manage_xyz.write_std_multixyz,
        driving_coords=driving_coordinates,        
    )
    
    # run pyGSM
    se_gsm.go_gsm()
    gsm_plot(se_gsm.energies, x=range(len(se_gsm.energies)), title=0)

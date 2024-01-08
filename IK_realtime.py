import argparse
import os
import threading
from time import sleep, time
import queue
from pathlib import Path
from qtm_interface import QTMInterface
from Exp_gui import EXPgui
# from QTgui import
# from PyQt5.QtWidgets import QApplication
from biosiglive import (
    MskFunctions,
    LivePlot,
    PlotType,
    InterfaceType
)

import biorbd as brbd
import asyncio as aio
import qtm_rt as qtm
from scipy.spatial.transform import Rotation as R
from osim_to_biomod import Converter, MuscleType, MuscleStateType
import numpy as np
from Parameters import osim_path

import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse

class manage_queue:
    def __init__(self, queue):
        self.is_running = True
        self.thread = threading.Thread(target=self.listen)
        self.queue = queue
        self.thread.start()

    def listen(self):
        while self.is_running:
            self.queue.put(input())

    def stop(self):
        self.is_running = False

async def generate_scaled_biomod(osim_path=None):
    biomod_path = str(Path(osim_path).parent / Path(osim_path).stem) + '.bioMod'
    converter = Converter(
        biomod_path,
        osim_path,
        ignore_muscle_applied_tag=False,
        ignore_fixed_dof_tag=False,
        ignore_clamped_dof_tag=False,
        mesh_dir=str(Path(osim_path).parent) + '/Geometry',
        skip_muscle=True,
        print_general_informations=True,
    )
    converter.convert_file()
    return biomod_path

async def update_ellipse(cE, q, GH_q1_ref, GH_q2_ref, center=[0,0], rx=1, ry=1, ax=None):
    cE.set_center(center)
    cE.set_width(width=(q[11]-GH_q1_ref)*rx)
    cE.set_height(height=(q[12]-GH_q2_ref)*ry)

async def set_zero_position(interface, biomod_path, marker_order, in_queue):
    #todo: save ref positions
    print('Set the participant in the starting position')
    # marker_plot = LivePlot(name='markers', plot_type=PlotType.Scatter3D)
    # marker_plot.init()
    while 1:
        try:
            in_queue.get_nowait()
            break
        except:
            await aio.sleep(0.1)
    while 1:
        mark_tmp, _ = await interface.get_marker_set_data(marker_names=interface.marker_sets[0].marker_names,
                                                          update_marker_order=True,
                                                          target_marker_list=marker_order)

        q_ref, qdot = await interface.get_kinematics_from_markers(model_path=biomod_path,
                                                              marker_set_name='markers',
                                                              kin_data_window=2,
                                                              get_markers_data=True,
                                                              method='biorbd_least_square', #'biorbd_kalman',
                                                                  # #biorbd_least_square'
                                                              initial_q = None, #[0,0,0,0,0,0,
                                                              #              0,0,
                                                              #              0,0,0,
                                                              #              -0.61,-1.41,-1,
                                                              #              1,0,
                                                              #              0,0
                                                              #              ],
                                                                  )
        # marker_plot.update(mark_tmp[:,:,-1].T, size=0.03)

        print(f'The zero position is defined as:'
              f'GH_q1: {np.rad2deg(q_ref[11][0])},'
              f'GH_q2: {np.rad2deg(q_ref[12][0])},'
              f'Elbow: {np.rad2deg(q_ref[14][0])}')
        while 1:

            import bioviz
            biorbd_viz = bioviz.Viz(biomod_path)
            biorbd_viz.load_movement(q_ref)
            biorbd_viz.exec()
            print(';oolah')

            try:
                ref_decision = in_queue.get_nowait()
                break
            except:
                await aio.sleep(0.1)
        if ref_decision == 'Ok':
            print('Accepted ref position')
            break
    return q_ref


async def main(to_create_biomod = True, osim_path=None, biomod_path=None,
               qtm_ip="127.0.0.1", qtm_pwd='password', in_queue = None, axes=None, fig=None):

    # Generate model and initiate interface
    if to_create_biomod:
        biomod_path = await generate_scaled_biomod(osim_path)

    model = brbd.Model(biomod_path)
    markers_order_biomod = [model.markerNames()[i].to_string() for i in range(len(model.markerNames()))]
    print(f'Loaded {biomod_path}')
    # GH_transformation_body = [[i, iseg] for i, iseg in enumerate(model.segments()) if
    #                           iseg.name().to_string()=='ulna_parent_offset'][0]
    # glenoid_body = [[i, iseg] for i, iseg in enumerate(model.segments()) if
    #                           iseg.name().to_string() == 'humerus_translation'][0]
    # gh_seq = 'xyz'

    # interface = InterfaceType.Custom

    interface = await QTMInterface(system_rate=100, ip=qtm_ip, init_now=True)

    n_markers = 33 #42

    await interface.add_marker_set(
        nb_markers=n_markers,
        data_buffer_size=100,
        marker_data_file_key="markers",
        name="markers",
        rate=100,
        unit="mm"
    )
    print('Marker set added')

    await start_moving(interface, biomod_path=biomod_path, marker_order=markers_order_biomod, in_queue=in_queue,
                       axes=axes, fig=fig)
    print('Experiment ended')

async def start_moving(interface, biomod_path, marker_order, in_queue, axes, fig):
    GH_q1_ref = 0
    GH_q2_ref = 0
    await set_zero_position(interface, biomod_path, marker_order,  in_queue)
    plt.ion()
    fdbck_ellipse = Ellipse((0,0),
                      width=3,
                      height=3,
                      facecolor='b',
                      edgecolor='none',
                      alpha=0.3)
    axes.add_patch(fdbck_ellipse)
    fig.canvas.draw()
    fig.canvas.flush_events()

    if not in_queue.empty():
        in_queue.get()

    while 1:
        await interface.get_marker_set_data(marker_names=interface.marker_sets[0].marker_names)
        q, qdot = await interface.get_kinematics_from_markers(model_path=biomod_path,
                                                              marker_set_name='markers',
                                                              kin_data_window=1,
                                                              get_markers_data=True,
                                                              method='biorbd_least_square',)

        await update_ellipse(fdbck_ellipse, q,
                           GH_q1_ref=GH_q1_ref,
                           GH_q2_ref=GH_q2_ref,
                           ax=axes)
        fig.canvas.draw()
        fig.canvas.flush_events()
        try:
            in_queue.get_nowait()
            break
        except:
            await aio.sleep(0.1)
        print('out?')
        if not in_queue.empty():
            in_queue.get()
            print('2nd block')
            break

    # interface.marker_sets[0].kin_method = 'biorbd_least_square' #, 'biorbd_kalman', 'biorbd_least_square'

    while 1:
        q, qdot = await interface.get_kinematics_from_markers(model_path=biomod_path,
                                                              marker_set_name='markers',
                                                              kin_data_window=5,
                                                              get_markers_data=True,
                                                              method='biorbd_least_square')
        # humerus


        if not in_queue.empty():
            in_queue.get()
            break
    await print('out')
        # loop_time = time() - tic
        # real_time_to_sleep = time_to_sleep - loop_time
        # if real_time_to_sleep > 0:
        #     sleep(real_time_to_sleep)

if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(description='Start experiment')
    PARSER.add_argument('-ip', '--qtmip', dest='qtmip', default="127.0.0.1")
    PARSER.add_argument('-par', '--participant', dest='ipar', default='0',
                        help='Choose a similar name to the one used when creating the subject '
                             'folder in the QTM project')
    PARSER.add_argument('--password', dest='password', default='password',
                        help='QTM streaming password')
    ARGS = PARSER.parse_args()
    in_queue = queue.Queue(maxsize=2)
    gui_input = manage_queue(queue=in_queue)
    use_gui = True
    if use_gui:
        loop = aio.new_event_loop()
        # app = QApplication([])
        app = EXPgui(loop, ARGS, main, in_queue=in_queue)
        loop.run_forever()
    else:
        loop = aio.get_event_loop()
        loop.run_until_complete(main(
            to_create_biomod=False,
            osim_path=osim_path,
            biomod_path="D:\Shoulder_ER_IR\Analysis\\results\\00IB\\_models\\wu_na_scaled_markers.bioMod",
            in_queue=in_queue),
        )
        loop.close()
    gui_input.stop()
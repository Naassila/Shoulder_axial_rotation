from typing import Union
import numpy as np
import asyncio as aio
import xml.etree.ElementTree as et
from biosiglive import(
    GenericInterface,
    InterfaceType,
    RealTimeProcessing,
    OfflineProcessing,
    MskFunctions,
)

try:
    import qtm_rt as qtm
except ModuleNotFoundError:
    pass

class QTMInterface(GenericInterface):
    def __init__(self, system_rate:float=100, ip:str= "127.0.0.1", init_now=True):
        super().__init__(system_rate=system_rate, interface_type=InterfaceType.Custom)
        self.address = ip
        self.devices = []
        self.marker_set = []
        self.offline_data = None
        self.init_now = init_now

    def __await__(self):
        return self._init_client().__await__()

    async def _init_client(self, realtime =False):
        if self.init_now:
            print(f"Connection to Qualisys sdk at: {self.address}")
            connection = await qtm.connect(self.address)
            current_state = await connection.get_state()
            if not (current_state.value == 8 or current_state.value == 3):
                if realtime:
                    await connection.new()
                else:
                    await connection.start(rtfromfile=True)
            if connection is None:
                print("Failed to connect to QTM")
                raise Exception('No available qtm connection')
            else:
                self.connection = connection
        return self

    async def add_marker_set(
        self,
        nb_markers: int,
        name: str = None,
        data_buffer_size: int = None,
        marker_names = None,
        rate: float = 100,
        unlabeled: bool = False,
        subject_name: str = None,
        kinematics_method= None,
        **kin_method_kwargs,
    ):
        """
        Add markers set to stream from the Qualisys system.

        Parameters
        ----------
        nb_markers: int
            Number of markers.
        name: str
            Name of the markers set.
        data_buffer_size: int
            Size of the buffer for the markers set.
        marker_names: Union[list, str]
            List of markers names.
        rate: int
            Rate of the markers set.
        unlabeled: bool
            Whether the markers set is unlabeled.
        subject_name: str
            Name of the subject. If None, the subject will be the first one in Nexus.
        kinematics_method: InverseKinematicsMethods
            Method used to compute the kinematics.
        **kin_method_kwargs
            Keyword arguments for the kinematics method.
        """
        if len(self.marker_sets) != 0:
            raise ValueError("Only one marker set can be added for now.")

        markers_tmp = self._add_marker_set(
            nb_markers=nb_markers,
            name=name,
            marker_names=marker_names,
            rate=rate,
            unlabeled=unlabeled,
            kinematics_method=kinematics_method,
            **kin_method_kwargs,
        )
        if self.connection:
            markers_qtm = await self.connection.get_parameters(['3d'])
            markers_xml = et.fromstring(markers_qtm)
            labels = []
            for i, ilabel in enumerate(markers_xml.findall('The_3D')[0].findall('Label')):
                labels.append(ilabel.findall('Name')[0].text)
            if len(labels) != nb_markers:
                raise RuntimeError("Number of markers extracted from the qtm file not as expected")

            markers_tmp.subject_name = 'No subject name in QTM'
            markers_tmp.marker_names = labels
        else:
            # to do
            pass
        markers_tmp.data_windows = data_buffer_size
        self.marker_sets.append(markers_tmp)

    async def get_marker_set_data(
            self,
            subject_name: Union[str, list] = None,
            marker_names: Union[str, list] = None,
            marker_indices: Union[int, list] = None,
            get_frame: bool = True,
            update_marker_order: bool = False,
            target_marker_list: Union[str, list] = None,
    ):
        """
        Get the markers data from QTM.

        Parameters
        ----------
        subject_name: Union[str, list]
            Name of the subject. If None, the subject will be the first one in Nexus.
        marker_names: Union[str, list]
            List of markers names.
        get_frame: bool
            Whether to get a new frame or not.
        update_marker_order: bool
            Account for changes in marker order between the biomod and the qtm file
        target_marker_list: Union[str, list]
            Target marker order to align with the biomod file

        Returns
        -------
        markers_data: list
            All asked markers data.
        """
        if len(self.marker_sets) == 0:
            raise ValueError("No marker set has been added to the QTM system.")
        if get_frame:
            self.get_frame()
            frame_data = await self.connection.get_current_frame(['3d'])
            pos = np.array(frame_data.get_3d_markers()[1]) * 1e-3 #TODO: check unit of data
            frame = frame_data.timestamp

        if target_marker_list:
            if marker_names == target_marker_list:
                update_marker_order = False
            else:
                update_marker_order = True
                new_indices = [marker_names.index(i) for i in target_marker_list]
                for mark in self.marker_sets:
                    mark.indices = new_indices

        marker_names=target_marker_list

        if marker_names and isinstance(marker_names, list):
            marker_names = [marker_names]

        all_markers_data = []

        for markers in self.marker_sets:
            markers.new_data = np.zeros((3, len(markers.marker_names), markers.sample))
            markers_data = np.zeros((3, len(markers.marker_names), markers.sample))
            for i, imark in enumerate(markers.indices):
                markers_data[:, i, :] = pos.T[:, imark, np.newaxis]
                markers.new_data[:, i, :] = pos.T[:, imark, np.newaxis]

            all_markers_data.append(markers_data)
            markers.append_data(pos)

        if len(all_markers_data) == 1:
            return all_markers_data[0], frame
        return all_markers_data, frame

    async def get_kinematics_from_markers(
        self,
        marker_set_name: str,
        model_path: str = None,
        method: Union[list, str] = 'kalman',
        custom_func: callable = None,
        **kwargs,
    ):
        """
        Get the kinematics from markers.

        Parameters
        ----------
        marker_set_name: str
            name of the markerset.
        model_path: str
            biorbd model of the kinematics.
        method: str
            Method to use to get the kinematics. Can be "kalman" or "custom".
        custom_func: function
            Custom function to get the kinematics.


        Returns
        -------
        kinematics: list
            List of kinematics.
        """
        marker_set_idx = [i for i, m in enumerate(self.marker_sets) if m.name == marker_set_name][0]
        return self.marker_sets[marker_set_idx].get_kinematics(model_path, method,
                                                                      custom_func=custom_func,
                                                                      **kwargs)
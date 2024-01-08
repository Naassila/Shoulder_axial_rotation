import tkinter as tk
import customtkinter as ctk
import os
import sys
from pathlib import Path

import asyncio as aio
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class FeedbackWindow(ctk.CTkToplevel):
    def __init__(self):
        super().__init__()
        self.geometry("300x500")

        self.title('Feedback')
        fig, axes = plt.subplots(1,1)
        axes.set_ylim(-10, 10)
        axes.set_xlim(-10, 10)
        self.axes=axes
        plt.axis('off')
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        fig = plt.gcf()
        self.fig = fig

class StandardParamFrame(ctk.CTkFrame):
    def __init__(self, master, ARGS):
        super().__init__(master)
        self.ARGS = ARGS
        self.grid_columnconfigure(0, weight=1)
        # self.grid_rowconfigure((0, weight=1)

        self.title = ctk.CTkLabel(self, text='Session parameters', fg_color="gray70", corner_radius=6)
        self.title.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")

        self.ip_text = ctk.CTkEntry(self,
                                    placeholder_text=ARGS.qtmip,
                                    # width=140,
                                    # height=28,
                                    corner_radius=0, )
        self.ip_text.insert(0, ARGS.qtmip)
        self.ip_label = ctk.CTkLabel(master=self,
                                     text='QTM IP address (by default local)')

        self.pwd_text = ctk.CTkEntry(master=self,
                                     placeholder_text=ARGS.password,
                                     # width=140,
                                     # height=28,
                                     corner_radius=0)
        self.pwd_text.insert(0, ARGS.password)
        self.pwd_label = ctk.CTkLabel(master=self,
                                      text='QTM password')

        self.part_text = ctk.CTkEntry(master=self,
                                      placeholder_text=str(ARGS.ipar),
                                      # width=140,
                                      # height=28,
                                      corner_radius=0)
        self.part_text.insert(0, str(ARGS.ipar))
        self.part_label = ctk.CTkLabel(master=self,
                                      text='Participant ID')

        for iitem, item in enumerate([self.part_label, self.part_text,self.ip_label,
                                      self.ip_text,self.pwd_label,self.pwd_text ]):
            item.grid(row=iitem+1, column=0, sticky='ew')

    def get(self):
        attis = ['ipar', 'qtmip', 'password']
        buttons = [self.part_text, self.ip_text, self.pwd_text,]
        for att, butt in zip(attis, buttons):
            setattr(self.ARGS, att, butt.get())

class MyRadiobuttonFrame(ctk.CTkFrame):
    def __init__(self, master, values):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.values = values
        self.title = 'Which model type is available to use ?'
        self.radiobuttons = []
        self.variable = ctk.StringVar(value="")
        self.model_loc=None

        self.title = ctk.CTkLabel(self, text=self.title, fg_color="gray70", corner_radius=6)
        self.title.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 0), sticky="ew")

        for i, value in enumerate(self.values):
            radiobutton = ctk.CTkRadioButton(self, text=value, value=value, variable=self.variable)
            radiobutton.grid(row=1, column=i, padx=10, pady=(10, 0), sticky="ew")
            self.radiobuttons.append(radiobutton)

        self.button_model_path = ctk.CTkButton(master=self,
                                          text='Confirm',
                                          command=self.add_path_frame,
                                          corner_radius=0)
        self.button_model_path.grid(row=3, column=0, columnspan=3, padx=(10, 10), pady=(10, 10), sticky="ew")

    def add_path_frame(self):
        self.model_path = ctk.CTkEntry(self,
                                       placeholder_text='D:\Shoulder_ER_IR\Analysis\\results\\00IB\\_models'
                                                        '\\wu_na_scaled_markers.bioMod',
                                       # 'Enter model location',
                                       )
        self.model_path.insert(0, 'D:\Shoulder_ER_IR\Analysis\\results\\00IB\\_models\\wu_na_scaled_markers.bioMod')
        self.model_path.grid(row=4, column=0, columnspan=3,)
        return self.model_path.get()

    def get_mod_path(self):
        self.model_loc = self.model_path.get()

    def get(self):
        return self.variable.get()

    def set(self, value):
        self.variable.set(value)

class EXPgui(ctk.CTk):

    def __init__(self, loop, ARGS, func, in_queue):
        super().__init__()
        self.loop = loop
        self.args = ARGS
        self.func = func
        self.in_queue = in_queue
        self.visual_fdbck = None
        self.protocol('WM_DELETE_WINDOW', self.close)
        sys.stdout.write = self.redirector

        current_dir = os.path.dirname(os.path.realpath(__file__))

        self.title('Shoulder axial rotation trainer')
        self.geometry("500x540")
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.parameters_frame = StandardParamFrame(self, self.args)
        self.parameters_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky='nsew')

        self.model_type = MyRadiobuttonFrame(self, values=["Osim", "BioMod"])
        self.model_type.grid(row=0, column=1, padx=(0, 10), pady=(10, 0), sticky="nsew")

        self.output_box = ctk.CTkTextbox(master=self)
        self.output_box.grid(row=10, column = 0, columnspan=3, padx=(10, 10), pady=(10, 0), sticky="ew")

        self.init_position = ctk.CTkButton(master=self,
                                               text='Define feedback ref',
                                               command=self.set_init_position,
                                               corner_radius=0)

        self.init_position.grid(row=11, column=0, columnspan=3, pady=(5, 5))

        self.button_start = ctk.CTkButton(master=self,
                                          text='Start experiment',
                                          command=self.start_experiment,
                                          corner_radius=0)

        self.button_start.grid(row=12, column=0, columnspan=3, pady=(5, 5))

        self.button_stop = ctk.CTkButton(master=self,
                                         text='Stop experiment',
                                         command=self.stop_experiment,
                                         corner_radius=0)
        self.button_stop.grid(row=13, column=0, columnspan=3, pady=(5, 5))

        self.accept_button = ctk.CTkButton(master=self,
                                         text='✓',
                                         command=self.accepted,
                                         corner_radius=0)
        self.accept_button.grid(row=12, column=2, columnspan=1, pady=(5, 5))

        self.tasks = []
        self.tasks.append(self.loop.create_task(self.updater(1/120)))


    def start_experiment(self):
        osim_path = None
        biomod_path = None

        self.parameters_frame.get()
        mod_type = self.model_type.get()
        self.model_type.get_mod_path()
        mod_path = self.model_type.model_loc


        if mod_type.lower() == 'osim':
            to_create_biomod=True
            osim_path = mod_path
            if os.path.splitext(Path(osim_path))[1]!='.osim':
                print(os.path.splitext(Path(osim_path))[1])
                print('Error: Path needs to point to an osim')
        else:
            to_create_biomod=False
            biomod_path = mod_path
            if os.path.splitext(Path(biomod_path))[1]!='.bioMod':
                print('Error: Path needs to point to a bioMod')

        if self.visual_fdbck is None or not self.visual_fdbck.winfo_exists():
            self.visual_fdbck = FeedbackWindow()  # create window if its None or destroyed
        else:
            self.visual_fdbck.focus()

        task = self.loop.create_task(
            self.func(
                to_create_biomod=to_create_biomod,
                osim_path=osim_path,
                biomod_path=biomod_path,
                qtm_ip=self.args.qtmip,
                qtm_pwd=self.args.password,
                in_queue=self.in_queue,
                axes=self.visual_fdbck.axes,
                fig=self.visual_fdbck.fig
                                        ))

        self.tasks.append(task)
        self.experiment = task

    def set_init_position(self):
        self.in_queue.put('')
        print('Reset the zero pose')

    def accepted(self):
        self.in_queue.put('Ok')

    def stop_experiment(self):
        if self.experiment is not None:
            print('Closing experiment')
            self.experiment.cancel()
            self.experiment = None

    async def updater(self, interval):
        while True:
            self.update()
            await aio.sleep(1e-5)

    def close(self):
        for task in self.tasks:
            task.cancel()
        self.loop.stop()
        self.destroy()

    def redirector(self, inputStr):
        self.output_box.insert('1.0', inputStr)

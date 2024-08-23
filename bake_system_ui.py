import tkinter
from tkinter import ttk
from matplotlib.backends.backend_tkagg import (
FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure
import numpy as np

from bake_system import System
import constants
import funcs

class SystemUI:
    """
    A class to display the UI for a bake system in a tkinter-based GUI.
    """
    def __init__(self, system : System, root : tkinter.Tk, notebook : ttk.Notebook):
        self.system = system
        self.root = root
        self.notebook = notebook

        self.updateEachIteration = True
        self.timeSinceLastUIUpdate = 0

        self.tab = tkinter.Frame(self.notebook)
        self.notebook.add(self.tab, text="Heater tape {}".format(self.system.id + 1))
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.graphFrame = ttk.Frame(self.tab)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graphFrame)  # A tk.DrawingArea.
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.graphFrame)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)
        self.graphFrame.grid(row=0, column=0, sticky="nsew")

        self.controlFrame = ttk.Frame(self.tab)
        self.readingTempLabel = ttk.Label(self.controlFrame, text=constants.CURRENT_TEMP_STR.format(0))
        self.setTempLabel = ttk.Label(self.controlFrame, text=constants.SET_TEMP_STR.format(self.system.displayTemp))
        self.setTempIncrementButton = tkinter.Button(self.controlFrame, text="Increment", 
                                                command=lambda: self.increment_display_temp(1.0))
        self.setTempDecrementButton = tkinter.Button(self.controlFrame, text="Decrement",
                                                command=lambda: self.decrement_display_temp(1.0))
        self.readingRateLabel = ttk.Label(self.controlFrame, text=constants.CURRENT_RATE_STR.format(0))
        self.setRateLabel = ttk.Label(self.controlFrame, text=constants.SET_RATE_STR.format(self.system.displayRate))
        self.setRateIncrementButton = tkinter.Button(self.controlFrame, text="Increment",
                                                    command=lambda: self.increment_display_rate(0.1))
        self.setRateDecrementButton = tkinter.Button(self.controlFrame, text="Decrement",
                                                    command=lambda: self.decrement_display_rate(0.1))
        self.goingSetButton = tkinter.Button(self.controlFrame, text="Go", command=lambda: self.useSetValues())
        self.numPointsLabel = ttk.Label(self.controlFrame, text="Number of last visible data points: "+ str(self.system.current_num_points))
        self.numPoints10FewerButton = tkinter.Button(self.controlFrame, text="-10", command=lambda: self.changeNumPoints(-10))
        self.numPoints10MoreButton = tkinter.Button(self.controlFrame, text="+10", command=lambda: self.changeNumPoints(10))
        self.numPoints100FewerButton = tkinter.Button(self.controlFrame, text="-100", command=lambda: self.changeNumPoints(-100))
        self.numPoints100MoreButton = tkinter.Button(self.controlFrame, text="+100", command=lambda: self.changeNumPoints(100))
        self.setKiLabel = ttk.Label(self.controlFrame, text="Current integral: " + str(self.system.displayKi))
        self.setKiIncrementButton = tkinter.Button(self.controlFrame, text="Increment",
                                                    command=lambda: self.increment_display_ki(0.1))
        self.setKiDecrementButton = tkinter.Button(self.controlFrame, text="Decrement",
                                                    command=lambda: self.decrement_display_ki(0.1))
        self.updateEveryLabel = ttk.Label(self.controlFrame, text="Update every")
        self.updateEveryIterationButton = tkinter.Button(self.controlFrame, text="Iteration", command=lambda: self.setUpdateEachIteration(True))
        self.updateEveryMinuteButton = tkinter.Button(self.controlFrame, text="Minute", command=lambda: self.setUpdateEachIteration(False))
        
        self.controlFrame.grid(row=0, column=1, sticky="nsew")
        self.setTempLabel.grid(row=0, column=0, sticky="nsew", columnspan=4)
        self.readingTempLabel.grid(row=1, column=0, sticky="nsew", columnspan=4)
        self.setTempIncrementButton.grid(row=2, column=2, sticky="nsew", columnspan=2)
        self.setTempDecrementButton.grid(row=2, column=0, sticky="nsew", columnspan=2)
        self.setRateLabel.grid(row=3, column=0, sticky="nsew", columnspan=4)
        self.readingRateLabel.grid(row=4, column=0, sticky="nsew", columnspan=4)
        self.setRateIncrementButton.grid(row=5, column=2, sticky="nsew", columnspan=2)
        self.setRateDecrementButton.grid(row=5, column=0, sticky="nsew", columnspan=2)
        self.setKiLabel.grid(row=6, column=0, sticky="nsew", columnspan=4)
        self.setKiIncrementButton.grid(row=7, column=2, sticky="nsew", columnspan=2)
        self.setKiDecrementButton.grid(row=7, column=0, sticky="nsew", columnspan=2)
        self.numPointsLabel.grid(row=8, column=0, sticky="nsew", columnspan=4)
        self.numPoints100FewerButton.grid(row=9, column=0, sticky="nsew")
        self.numPoints10FewerButton.grid(row=9, column=1, sticky="nsew")
        self.numPoints10MoreButton.grid(row=9, column=2, sticky="nsew")
        self.numPoints100MoreButton.grid(row=9, column=3, sticky="nsew")
        self.goingSetButton.grid(row=10, column=0, sticky="nsew", columnspan=4)
        self.updateEveryLabel.grid(row=11, column=0, sticky="nsew")
        self.updateEveryIterationButton.grid(row=11, column=1, sticky="nsew")
        self.updateEveryMinuteButton.grid(row=11, column=2, sticky="nsew")
        self.tab.grid_rowconfigure(0, weight=1)
        self.tab.grid_columnconfigure(0, weight=2)
        self.tab.grid_columnconfigure(1, weight=1)

    def update(self, iterationNum : int, timeSinceLastIteration : float, storedTimes : list[float]) -> None:
        """
        Updates UI values based on the system's updated current state. Time is not managed by the system so it needs to
        be passed in.
        """
        
        shouldUpdate : bool = True
        if not self.updateEachIteration:    # update every minute
            self.timeSinceLastUIUpdate += timeSinceLastIteration
            if self.timeSinceLastUIUpdate < constants.TIME_TO_UPDATE_THE_UI_IF_NOT_EVERY_ITERATION:
                shouldUpdate = False

        if shouldUpdate:
            self.timeSinceLastUIUpdate = 0
            loc = iterationNum % constants.MAX_POINTS_IN_MEMORY
            readTemp = 0 if self.system.storedTemps[loc] == None else self.system.storedTemps[loc]
            # if self.system.storedTemps[loc] == None or self.system.storedTemps[loc - 2] == None else 
            calculatedRate = funcs.average_rate_of_change(
                funcs.rolling_moving_window(storedTimes, loc, min(iterationNum, self.system.current_num_points)),
                funcs.rolling_moving_window(self.system.storedTemps, loc, min(iterationNum, self.system.current_num_points))
            )
            self.readingTempLabel.config(text=constants.CURRENT_TEMP_STR.format(round(readTemp, 2)))
            self.readingRateLabel.config(text=constants.CURRENT_RATE_STR.format(round(calculatedRate * 60, 2)))

            # disable buttons if necessary
            if self.system.goingSet:
                self.goingSetButton.config(state=tkinter.DISABLED)
            else:
                self.goingSetButton.config(state=tkinter.NORMAL)

            if self.system.current_num_points <= 100:
                self.numPoints100FewerButton.config(state=tkinter.DISABLED)
            else:
                self.numPoints100FewerButton.config(state=tkinter.NORMAL)
            if self.system.current_num_points <= 10:
                self.numPoints10FewerButton.config(state=tkinter.DISABLED)
            else:
                self.numPoints10FewerButton.config(state=tkinter.NORMAL)
            if self.system.current_num_points >= constants.MAX_POINTS_IN_MEMORY - 100:
                self.numPoints100MoreButton.config(state=tkinter.DISABLED)
            else:
                self.numPoints100MoreButton.config(state=tkinter.NORMAL)
            if self.system.current_num_points >= constants.MAX_POINTS_IN_MEMORY - 10:
                self.numPoints10MoreButton.config(state=tkinter.DISABLED)
            else:
                self.numPoints10MoreButton.config(state=tkinter.NORMAL)
            
            self.ax.clear()
            storedTimeWindow = funcs.rolling_moving_window(storedTimes, loc - 1,
                                                            self.system.current_num_points)
            storedTempWindow = funcs.rolling_moving_window(self.system.storedTemps, loc - 1,
                                                            self.system.current_num_points)
            xInMin = (np.array(storedTimeWindow).astype(float)) / 60
            self.ax.plot(xInMin, storedTempWindow)
            self.ax.set_xlabel("Time (minutes)")
            self.ax.set_ylabel("Temperature (C)")
            self.ax.set_title("Measured temperature vs time heater tape {}".format(self.system.id + 1))
            self.fig.canvas.draw_idle()
    
    def increment_display_temp(self, amount : float) -> None:
        self.system.increment_display_temp(amount)
        self.setTempLabel.config(text=constants.SET_TEMP_STR.format(self.system.displayTemp))
        self.setTempDecrementButton.config(state=tkinter.NORMAL)
        if self.system.displayTemp >= constants.MAX_SET_TEMP:
            self.setTempIncrementButton.config(state=tkinter.DISABLED)
        self.goingSetButton.config(state=tkinter.NORMAL)
    
    def decrement_display_temp(self, amount : float) -> None:
        self.system.decrement_display_temp(amount)
        self.setTempLabel.config(text=constants.SET_TEMP_STR.format(self.system.displayTemp))
        self.setTempIncrementButton.config(state=tkinter.NORMAL)
        if self.system.displayTemp <= constants.MIN_SET_TEMP:
            self.setTempDecrementButton.config(state=tkinter.DISABLED)
        self.goingSetButton.config(state=tkinter.NORMAL)
    
    def increment_display_rate(self, amount : float) -> None:
        self.system.increment_display_rate(amount)
        self.setRateLabel.config(text=constants.SET_RATE_STR.format(self.system.displayRate))
        self.setRateDecrementButton.config(state=tkinter.NORMAL)
        if self.system.steppingUp:
            if self.system.displayRate >= constants.MAX_SET_RATE:
                self.setRateIncrementButton.config(state=tkinter.DISABLED)
        else:
            if self.system.displayRate >= -constants.MIN_SET_RATE:
                self.setRateIncrementButton.config(state=tkinter.DISABLED)
        self.goingSetButton.config(state=tkinter.NORMAL)
    
    def decrement_display_rate(self, amount : float) -> None:
        self.system.decrement_display_rate(amount)
        self.setRateLabel.config(text=constants.SET_RATE_STR.format(self.system.displayRate))
        self.setRateIncrementButton.config(state=tkinter.NORMAL)
        if self.system.steppingUp:
            if self.system.displayRate <= constants.MIN_SET_RATE:
                self.setRateDecrementButton.config(state=tkinter.DISABLED)
        else:
            if self.system.displayRate <= -constants.MAX_SET_RATE:
                self.setRateDecrementButton.config(state=tkinter.DISABLED)
        self.goingSetButton.config(state=tkinter.NORMAL)
    
    def increment_display_ki(self, amount : float) -> None:
        self.system.increment_display_ki(amount)
        self.setKiLabel.config(text=constants.SET_KI_STR.format(self.system.displayKi))
        self.setKiDecrementButton.config(state=tkinter.NORMAL)
        if self.system.displayKi >= constants.MAX_SET_KI:
            self.setKiIncrementButton.config(state=tkinter.DISABLED)
        self.goingSetButton.config(state=tkinter.NORMAL)
    
    def decrement_display_ki(self, amount : float) -> None:
        self.system.decrement_display_ki(amount)
        self.setKiLabel.config(text=constants.SET_KI_STR.format(self.system.displayKi))
        self.setKiIncrementButton.config(state=tkinter.NORMAL)
        if self.system.displayKi <= constants.MIN_SET_KI:
            self.setKiDecrementButton.config(state=tkinter.DISABLED)
        self.goingSetButton.config(state=tkinter.NORMAL)
    
    def useSetValues(self) -> None:
        self.system.useSetValues()
        self.setTempLabel.config(text=constants.SET_TEMP_STR.format(self.system.displayTemp))
        self.setRateLabel.config(text=constants.SET_RATE_STR.format(self.system.displayRate))
        self.setKiLabel.config(text=constants.SET_KI_STR.format(self.system.displayKi))
    
    def changeNumPoints(self, changeAmount : int) -> None:
        self.system.changeNumPoints(changeAmount)
        self.numPointsLabel.config(text="Number of last visible data points: " + str(self.system.current_num_points))
    
    def setUpdateEachIteration(self, shouldDoEachIteration : bool) -> None:
        self.updateEachIteration = shouldDoEachIteration
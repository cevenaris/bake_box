import tkinter
from tkinter import ttk
import time
import os
import sys
from multiprocessing import Process, Queue
import RPi.GPIO as GPIO

from libs.max6675 import MAX6675
import constants
from bake_system import System, SystemInoperableError, SystemUnreliableError
from bake_system_ui import SystemUI

# the main loop of the program
# does serial stuff first then parallel then back to serial
# serial stuff includes getting the time of the current iteration
# and updating the statuses of each system
# parallel stuff is each system gettings its temperature, calculating and running its duty cycle
def iterate(iterationNum : int, systemList : list[System], uiList : list[SystemUI], 
            tempDetectorDict : dict[System: MAX6675], start_time : float, root : tkinter.Tk, 
            notebook : ttk.Notebook, storedTimes : list[float], saveToFileName : str, 
            copyQueue : Queue, errorQueue : Queue)-> None:
    """
    The main loop that will be repeatedly called to run a bake. It starts out in serial to manage timing, 
    goes to parallel to run all systems at once, and then goes back to serial to update the UI and save data.
    At the end it calls itself using a GUI method (root.after)

    systemList: a list of all the systems that should be run
    uiList: a list of all the UIs corresponding to the systems
    tempDetectorDict: a dictionary mapping each system to its temperature detector
    start_time: the time that the program started running
    root: the tkinter root object
    notebook: the ttk notebook object
    storedTimes: an array of the times of each past iteration
    saveToFileName: the name of the file to save the data to
    copyQueue: holds all the updated system objects that need to be copied over to the original objects
    errorQueue: holds all the errors that need to be raised
    """
    loc = iterationNum % constants.MAX_POINTS_IN_MEMORY
    prevTime = (0 if storedTimes[loc] == None else storedTimes[loc]) + start_time
    currentTime = time.clock_gettime(time.CLOCK_MONOTONIC_RAW)
    lastIterationTime = currentTime - prevTime
    print("Time to run this iteration: ", round(lastIterationTime, 2), "seconds")
    timeElapsed = currentTime - start_time
    storedTimes[iterationNum % constants.MAX_POINTS_IN_MEMORY] = timeElapsed

    unreliableExceptions : list['SystemUnreliableError'] = []
    inoperableExceptions : list['SystemInoperableError'] = []

    # the actual parallel processing stage
    tasks : list[Process] = []
    for system in systemList:
        p = Process(target=run_system, args=(iterationNum, system, tempDetectorDict[system],
                                            timeElapsed, lastIterationTime, copyQueue,
                                            errorQueue))
        p.start()
        tasks.append(p)
    for p in tasks:
        p.join()
    
    # back in serial
    while not errorQueue.empty():
        e = errorQueue.get()
        if isinstance(e, SystemUnreliableError):
            unreliableExceptions.append(e)
        elif isinstance(e, SystemInoperableError):
            inoperableExceptions.append(e)

    if len(unreliableExceptions) > 0:
        raise ExceptionGroup("Systems became unreliable at device time {}.".format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(currentTime))), unreliableExceptions)
    
    
    # copying over the updated system object states to the original objects
    output = []
    for i in range(len(systemList)):
        output.append(copyQueue.get())
    
    for o in output:
        systemList[o[0]].copy(o[1])
    
    # turning off SSR capability in the original objects if necessary
    if len(inoperableExceptions) > 0:
        print("The following systems became inoperable at device time {}. ".format(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(currentTime))))
        for e in inoperableExceptions:
            print("\tSystem {}, cause: {}".format(e.systemID + 1, e.cause))
        print("Not running any more duty cycles on any SSRs; temperature monitoring will continue.")
        for system in systemList:
            system.operation_status = constants.OPERATION_STATUSES.INOPERABLE
    
    # updating only the visible system's ui
    index = notebook.index(notebook.select())
    uiList[index].update(iterationNum, lastIterationTime, storedTimes)

    # syncing set values across all systems

    # saving the data from each system to a file
    # times are synced across all systems, each system just adds its temperature
    if not os.path.exists(constants.SAVE_TO_FOLDER_STR):
        os.makedirs(constants.SAVE_TO_FOLDER_STR)
    with open(saveToFileName, "a+") as file:
        append_str = "{}".format(storedTimes[loc])
        for system in systemList:
            append_str += ",{}".format(system.storedTemps[loc])
        file.write(append_str + "\n")
        file.close()
    
    for system in systemList:
        if system.operation_status != constants.OPERATION_STATUSES.INOPERABLE:
            print('TAPE ', str(system.id + 1), '| Duty cycle length', ': ', 
                round(system.computedDutyCycle * 100, 2), ' percent of period')
    
    print("Iteration: {}".format(iterationNum))
    root.after(constants.TIME_BETWEEN_ITERATIONS, lambda: iterate(iterationNum + 1, systemList, uiList, tempDetectorDict, start_time, 
                                                                  root, notebook, storedTimes, saveToFileName, copyQueue, errorQueue))

# Let each system run itself (this will be called in parallel and will update its state)
# Due to the way that objects are passed in python in parallel, the updated system object
# and the original are not the same
# so put the updated system object in a queue to be copied over to the original system object
def run_system(iterationNum : int, system : System, tempDetector : MAX6675, timeElapsed : float, 
               lastIterationTime : float, copyQueue : Queue, errorQueue : Queue) -> None:
    """
    
    """
    # if timeElapsed > TOTAL_STARTUP_TIME and lastIterationTime < SET_PERIOD:
        # print(locals())
        # print(globals())
        # GPIO.cleanup()
        # _quit()
    sys, errList = system.run(iterationNum, timeElapsed, tempDetector, lastIterationTime)
    copyQueue.put((sys.id, sys))
    for e in errList:
        errorQueue.put(e)

if __name__ == "__main__":
    start_time = time.clock_gettime(time.CLOCK_MONOTONIC_RAW)
    start_timestr = time.strftime("%Y%m%d-%H%M%S")
    storedTimes = [None] * constants.MAX_POINTS_IN_MEMORY
    saveToFileName = constants.SAVE_TO_FOLDER_STR + "/plot_data_{}.csv".format(start_timestr)

    root = tkinter.Tk()
    root.wm_title("Bake Box Temperature Control System")
    notebook = ttk.Notebook(root)
    notebook.pack(expand=1, fill="both")

    def _quit() -> None:
        GPIO.cleanup()
        root.quit()     # stops mainloop
        root.destroy()  # this is necessary on Windows to prevent
                    # Fatal Python Error: PyEval_RestoreThread: NULL tstate
    
    def report_callback_exception(self, exc, val, tb):
        _quit()
        raise val
    
    tkinter.Tk.report_callback_exception = report_callback_exception
    
    root.protocol("WM_DELETE_WINDOW", _quit)

    GPIO.setmode(GPIO.BOARD)

    # check for initialization arguments
    initialTemps = []
    initialRates = []
    initialKis = []
    initializationArgs = sys.argv[1:]
    if len(initializationArgs) == 0:
        pass
    elif len(initializationArgs) == 4:
        for i in range(4):
            initialTemps.append(float(initializationArgs[i]))
    elif len(initializationArgs) == 8:
        for i in range(4):
            initialTemps.append(float(initializationArgs[i]))
        for i in range(4, 8):
            initialRates.append(float(initializationArgs[i]))
    elif len(initializationArgs) == 12:
        for i in range(4):
            initialTemps.append(float(initializationArgs[i]))
        for i in range(4, 8):
            initialRates.append(float(initializationArgs[i]))
        for i in range(8, 12):
            initialKis.append(float(initializationArgs[i]))
    else:
        raise ValueError("Invalid number of arguments passed to program")

    # create the systems
    system1 = System(0, constants.RELAY_SELECT.RS1)
    system2 = System(1, constants.RELAY_SELECT.RS2)
    system3 = System(2, constants.RELAY_SELECT.RS3)
    system4 = System(3, constants.RELAY_SELECT.RS4)
    systemList = [system1, system2, system3, system4]
    ui1 = SystemUI(system1, root, notebook)
    ui2 = SystemUI(system2, root, notebook)
    ui3 = SystemUI(system3, root, notebook)
    ui4 = SystemUI(system4, root, notebook)
    uiList = [ui1, ui2, ui3, ui4]

    # create the temperature detector objects
    tempDetector1 = MAX6675(constants.CHIP_SELECT.CS1, constants.CLOCK_PINS.CLK1, 
                            constants.DATA_PINS.DATA1, units="c", board=GPIO.BOARD)
    tempDetector2 = MAX6675(constants.CHIP_SELECT.CS2, constants.CLOCK_PINS.CLK2, 
                            constants.DATA_PINS.DATA2, units="c", board=GPIO.BOARD)
    tempDetector3 = MAX6675(constants.CHIP_SELECT.CS3, constants.CLOCK_PINS.CLK3,
                            constants.DATA_PINS.DATA3, units="c", board=GPIO.BOARD)
    tempDetector4 = MAX6675(constants.CHIP_SELECT.CS4, constants.CLOCK_PINS.CLK4,
                            constants.DATA_PINS.DATA4, units="c", board=GPIO.BOARD)
    tempDetectorDict = {system1: tempDetector1, system2: tempDetector2, 
                        system3: tempDetector3, system4: tempDetector4}

    copyQueue = Queue()
    errorQueue = Queue()

    waiting_window = tkinter.Toplevel(root)
    waiting_window.geometry("300x200")
    waiting_window.title("Please wait")
    waiting_window.transient(root)
    waiting_window.grab_set()
    root.update_idletasks()
    root.update()
    x = root.winfo_x() + (root.winfo_height() // 2) - (300 // 2)
    y = root.winfo_y() + (root.winfo_width() // 2) - (200 // 2)
    waiting_window.geometry("+{}+{}".format(x, y))
    wait_label = ttk.Label(waiting_window, text="Starting program, please wait until this window disappears")
    wait_label.pack(expand=True)
    # wait_label.attributes("-topmost", True)

    def startup_wait():
        root.after(constants.TOTAL_STARTUP_TIME * 1000, lambda: waiting_window.destroy())

    # actually starting up the program
    root.after(0, startup_wait)
    root.after(constants.TOTAL_STARTUP_TIME * 1000, lambda: iterate(0, systemList, uiList, tempDetectorDict, 
                                                          start_time, root, notebook, 
                                                          storedTimes, saveToFileName, 
                                                          copyQueue, errorQueue))

    try:
        root.mainloop()
    except ExceptionGroup as e: # should only happen if there are unreliable systems the inoperable
        # system exceptions should be handled in iterate itself
        for exc in e.exceptions:
            print(exc)
        print("Shutting down the program in response to at least one system becoming unreliable.")
    except KeyboardInterrupt:
        print("Shutting down the program in response to a keyboard interrupt.")
    finally:
        GPIO.cleanup()
    
# TODO: 
"""
- swap out the RTDs for thermocouples - done
- decide which gpio pins make sense for each type and system - done
- test out each set of gpio pins
  - Set 1: works
  - Set 2: works
  - Set 3: works
  - Set 4: works
- test out all SSRs - done, all functional
- test out all the MAX6675 amplifiers - done, all functional
- test out all the thermocouples - done, 3 functional
- test out all the wall plugs - done, all functional
- test out parallelism with thermocouples - done, works
- make the ui faster by only updating the graph for the system that is selected - done
- make the ui fit better (vertical stacking, one go button) - done
- set up error raising and handling - tested
- solder stuff to the pi backpack - done
- ensure that variac can output enough power to run 4 SSRs at once - done
- bake a single large piece of metal - testing
- change the current rate reading to be a rolling average - to test
- add command line args for setting the initial set temperature, rate, and ki - to test
- make options to switch between the graph updating every iteration and minute - to do
- create a shortcut to the program on the pi - to do
- make a single directory where plot data will be stored - to do
- create the user manual - in progress
- upload the code to github - to do
- finish the cad model including hole guides - in progress
- cut out holes in the case - not started
- fix the graph being like 2 values behind the current printed temperature value - to do
- change the set values to be shared among all the systems - to do
"""
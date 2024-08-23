from RPi import GPIO
import math
import time

import constants
import funcs
from libs.max6675 import MAX6675, MAX6675Error

# Stores all the data for a single system
# Including the relay the system controls
# and all state values
# all the logic can be done with this class
class System:
    """Stores all the data for a single bake system, including the relay the system controls and all state values. 
    Given just this object and a temperature detector, the system can run itself for an iteration."""
    def __init__(self, id : int, relay : constants.RELAY_SELECT, startSetTemp : int=150,
                 startSetRate : float=1.0, startSetKi : float=1.5):
        """Create a system object with a given relay and initial set temperature, rate, and integral constant values. 
        The id is a numeric identifier that corresponds to the position of the system in a list with all other systems."""
        self.id = id
        self.relay = relay

        self.storedTemps = [None] * constants.MAX_POINTS_IN_MEMORY
        self.prev_error = 0
        self.error_running_sum = 0
        self.tempForDutyCycle = 0
        self.computedDutyCycle = 0
        self.desiredTemp = startSetTemp
        self.desiredRate = startSetRate
        self.stepToTemp = startSetTemp
        self.ki = startSetKi
        self.numStepsTaken = 0
        self.hasSteppedToDesired = False
        self.hasReachedDesired = False
        self.timeSinceLastStep = 0
        self.steppingUp = True
        self.maxAcceptableTemp = self.desiredTemp + 10
        self.timeOutOfAcceptableRange = 0
        self.operation_status = constants.OPERATION_STATUSES.OPERABLE

        self.displayTemp = self.desiredTemp
        self.displayRate = self.desiredRate
        self.displayKi = self.ki
        self.goingSet = True
        self.current_num_points = constants.STARTING_NUM_POINTS   # how many points to display on the graph
        self.updateDataEveryMinute = False  # if false, update every iteration
        self.timeSinceLastUpdate = 0

        GPIO.setup(self.relay, GPIO.OUT)
    
    # does everything for 1 iteration of the system
    # but cannot modify the original system variable passed in
    # instead returns a new system variable that can be copied into the original
    def run(self, iterationNum : int, timeElapsed : float, tempDetector : MAX6675, 
            lastIterationTime : float, sharedVals : 'SystemSharedValues'=None) -> tuple['System', list[Exception]]:
        """
        Does everything for 1 iteration of the bake system: reads in temperature data, runs the PID algorithm,
        controls the SSR, and updates the system's state. 

        timeElapsed: the time elapsed since the start of the program
        tempDetector: the temperature detector object that reads in the temperature data
        lastIterationTime: the time it took to complete the last iteration of the program
        sharedVals: for systems heating the same object, used to sync values across them all. This
        is to prevent creating a temperature gradient across the object. For independent systems, leave as None.

        returns: the system object itself and a list of exceptions that occurred during the iteration
        """

        # if values are shared use the shared values otherwise just have it be the same
        allSteppedToSame : bool = True
        if sharedVals != None:
            allSteppedToSame = sharedVals.allSteppedToSame
            self.desiredTemp = sharedVals.setTemp
            self.desiredRate = sharedVals.setRate
            self.ki = sharedVals.setKi
            self.updateDataEveryMinute = sharedVals.updateDataEveryMinute
            self.timeSinceLastUpdate = sharedVals.timeSinceLastUpdate


        collectedExceptions = []
        
        loc = iterationNum % constants.MAX_POINTS_IN_MEMORY
        prevTemp = (0 if self.storedTemps[loc - 1] == None else self.storedTemps[loc - 1])
        currentTemp : float
        try:
            currentTemp = tempDetector.get()
        except MAX6675Error as e:
            collectedExceptions.append(SystemUnreliableError(self.id, timeElapsed, e))
        else:
            # only store the temperature if the time is right (every iteration or every minute)

            if self.updateDataEveryMinute:
                if self.timeSinceLastUpdate >= 60:
                    self.timeSinceLastUpdate = 0
                    self.storedTemps[loc] = currentTemp

            if self.numStepsTaken == 0 and timeElapsed > constants.TOTAL_STARTUP_TIME:
                if self.steppingUp:
                    self.stepToTemp = math.ceil(currentTemp)
                else:
                    self.stepToTemp = math.floor(currentTemp)
                self.error_running_sum = 0
                self.prev_error = 0
                self.timeSinceLastStep = 0
                self.numStepsTaken = 1
                # for the very first step, go to the next degree

            if self.steppingUp:
                if self.timeSinceLastStep >= (60 / self.desiredRate) and currentTemp >= self.stepToTemp and allSteppedToSame:
                    if self.stepToTemp < self.desiredTemp:
                        self.numStepsTaken += 1
                        self.stepToTemp += 1
                        self.error_running_sum = 0
                        self.timeSinceLastStep = 0
                    elif self.stepToTemp == self.desiredTemp and not self.hasSteppedToDesired:
                        self.hasSteppedToDesired = True
                        self.error_running_sum = 0
                        self.timeSinceLastStep = 0
                if currentTemp >= self.desiredTemp:
                    # 0 out the error sum if the temperature is above the desired temperature
                    # because otherwise the integral term will accumulate a lot of error that will need to be undone
                    # and cooling is slow
                    # this situation could happen if the metal is done being heated up or if the set temperature
                    # is decreased
                    # but in either case this should help the integral term converge to the set temperature
                    self.error_running_sum = 0
            else:
                if self.timeSinceLastStep >= (60 / self.desiredRate) and currentTemp <= self.stepToTemp and allSteppedToSame:
                    if self.stepToTemp > self.desiredTemp:
                        self.numStepsTaken += 1
                        self.stepToTemp -= 1
                        self.error_running_sum = 0
                        self.timeSinceLastStep = 0
                    elif self.stepToTemp == self.desiredTemp and not self.hasSteppedToDesired:
                        self.hasSteppedToDesired = True
                        self.error_running_sum = 0
                        self.timeSinceLastStep = 0
                if currentTemp > self.stepToTemp:
                    # 0 out the error sum until the temperature drops to below the step temperature
                    # because otherwise it will accumulate negative error and will need to drop below
                    # the step for enough time to accumulate positive error
                    # just avoid that by zeroing out until it drops below the step 
                    self.error_running_sum = 0
            self.timeSinceLastStep += lastIterationTime

            # this is for safety
            # if the temperature is too far off for too long, give a signal to turn off all the SSRs
            # mainly to prevent overheating but in general just if the SSRs seem broken
            if currentTemp > self.maxAcceptableTemp or currentTemp < constants.MIN_ACCEPTABLE_TEMP:
                self.timeOutOfAcceptableRange += lastIterationTime
                if self.timeOutOfAcceptableRange >= constants.MAX_TIME_AT_UNACCEPTABLE_TEMP * 60:
                    if self.operation_status != constants.OPERATION_STATUSES.INOPERABLE:
                        tempReason = "high" if currentTemp > self.maxAcceptableTemp else "low"
                        collectedExceptions.append(SystemInoperableError(self.id, timeElapsed, 
                                                    " the temperature reading being too " + tempReason + " for too long"))
                    self.operation_status = constants.OPERATION_STATUSES.INOPERABLE
                else:
                    self.operation_status = constants.OPERATION_STATUSES.ON_HOLD
            else:
                if self.operation_status != constants.OPERATION_STATUSES.INOPERABLE:  # if it was inoperable, don't change it
                    self.timeOutOfAcceptableRange = 0
                    self.operation_status = constants.OPERATION_STATUSES.OPERABLE

            # this is for stabilization
            # if the system gets too far from the step feature then start stepping again
            # shouldn't keep repeatedly hitting this because then the step temperature will change
            # to be within a degree of the current temperature
            # simulate a first step to achieve this
            if abs(self.stepToTemp - currentTemp) >= constants.LARGE_TEMP_DIFFERENCE:
                self.numStepsTaken = 0
                self.steppingUp = (self.desiredTemp > currentTemp)
            
            print(f"Time: {timeElapsed:.2f}, time since last step: {self.timeSinceLastStep:.2f}, Stepping to {self.stepToTemp}")

            # heating up the heater tape via duty cycle
            self.tempForDutyCycle = currentTemp
            self.compute_duty_cycle_from_temp()
            self.run_SSR_for_duty_cycle()

        return self, collectedExceptions
    
    # copies over the state variables of another system
    # used to update the original system after the copy is modified in parallel
    def copy(self, other : 'System') -> None:
        """
        Copies over state variables of another system to itself. Because systems are likely to be called in parallel, this
        is necessary to update the original objects after the copies are modified and returned from parallel processes.

        other: the other system object to copy from
        """
        self.storedTemps = other.storedTemps
        self.error_running_sum = other.error_running_sum
        self.tempForDutyCycle = other.tempForDutyCycle
        self.computedDutyCycle = other.computedDutyCycle
        self.desiredTemp = other.desiredTemp
        self.desiredRate = other.desiredRate
        self.stepToTemp = other.stepToTemp
        self.ki = other.ki
        self.numStepsTaken = other.numStepsTaken
        self.hasSteppedToDesired = other.hasSteppedToDesired
        self.hasReachedDesired = other.hasReachedDesired
        self.timeSinceLastStep = other.timeSinceLastStep
        self.steppingUp = other.steppingUp
        self.maxAcceptableTemp = other.maxAcceptableTemp
        self.timeOutOfAcceptableRange = other.timeOutOfAcceptableRange
        self.operation_status = other.operation_status

        self.displayTemp = other.displayTemp
        self.displayRate = other.displayRate
        self.displayKi = other.displayKi
        self.goingSet = other.goingSet
        self.current_num_points = other.current_num_points
        self.updateDataEveryMinute = other.updateDataEveryMinute
        self.timeSinceLastUpdate = other.timeSinceLastUpdate
    
    # Computes the duty cycle duration based on the output of the pid algorithm
    # Temperature is read -> run pid on reading
    # Use output of pid to calculate the duration of the duty cycle
    def compute_duty_cycle_from_temp(self) -> None:
        """
        Computes the duty cycle proportion based on the output of the PID algorithm ran on the state variables.
        The method automatically updates the error and computed duty cycle state values.
        """
        output_duty_cycle, output_error = funcs.pid(self.tempForDutyCycle, self.stepToTemp, self.prev_error, 
                                              self.error_running_sum, constants.KP, self.ki, constants.KD)
        output_duty_cycle = funcs.clamp(output_duty_cycle, 1.0, 0.0)
        self.computedDutyCycle = output_duty_cycle
        self.prev_error = output_error
        self.error_running_sum += output_error

    # GPIO pins set to high or low to turn the SSR on or off
    def SSR_on(self) -> None:
        GPIO.output(self.relay, GPIO.HIGH)

    def SSR_off(self) -> None:
        GPIO.output(self.relay, GPIO.LOW)

    # Runs the SSR for the duty cycle proportion of the period by turning the SSR
    # on, waiting, then turning the SSR off
    # but only if the system is in a good state
    # uses time.sleep so the GUI is not updated during this time
    def run_SSR_for_duty_cycle(self) -> None:
        """
        Runs the SSR for the duty cycle proportion of the period by turning the SSR on, waiting, then turning the SSR off.
        This method is blocking and uses time.sleep so the GUI is not updated during this time. It will only run the SSR if
        the system is not in an inoperable state.
        """
        if not self.operation_status == constants.OPERATION_STATUSES.INOPERABLE:
            self.SSR_on()
            time.sleep(constants.SET_PERIOD * self.computedDutyCycle)
            self.SSR_off()
            time.sleep(constants.SET_PERIOD - constants.SET_PERIOD * self.computedDutyCycle)
        else:
            time.sleep(constants.SET_PERIOD)
    
    # Display values may be different than the actual set values because
    # of how the user interface is set up
    # These change the display values which become the set values which the system tries to achieve
    # when the user hits the go button
    def increment_display_temp(self, amount : float) -> None:
        self.displayTemp = round(self.displayTemp + amount, 2)
        self.goingSet = False
    
    def decrement_display_temp(self, amount : float):
        self.displayTemp = round(self.displayTemp - amount, 2)
        self.goingSet = False
    
    def increment_display_rate(self, amount : float) -> None:
        self.displayRate = round(self.displayRate + amount, 2)
        self.goingSet = False
    
    def decrement_display_rate(self, amount : float) -> None:
        self.displayRate = round(self.displayRate - amount, 2)
        self.goingSet = False
    
    def increment_display_ki(self, amount : float) -> None:
        self.displayKi = round(self.displayKi + amount, 2)
        self.goingSet = False
    
    def decrement_display_ki(self, amount : float) -> None:
        self.displayKi = round(self.displayKi - amount, 2)
        self.goingSet = False
    
    def useSetValues(self) -> None:
        if self.displayTemp >= self.stepToTemp:  # decrease value
            self.steppingUp = True
            self.displayRate = abs(self.displayRate)
        else:   # increase value
            self.steppingUp = False
            self.displayRate = -abs(self.displayRate)
        
        self.hasSteppedToDesired = False
        self.hasReachedDesired = False
        self.desiredTemp = self.displayTemp
        self.numStepsTaken = 0
        self.maxAcceptableTemp = self.desiredTemp + constants.UNACCEPTABLE_TEMP_OVERSHOOT

        self.desiredRate = abs(self.displayRate)
        self.ki = self.displayKi

        self.goingSet = True
    
    def changeNumPoints(self, changeAmount : int) -> None:
        self.current_num_points += changeAmount

class SystemSharedValues:
    def __init__(self, allSteppedToSame : bool, setTemp : float, setRate : float, 
                 setKi : float, updateDataEveryMinute : bool, timeSinceLastUpdate : float):
        self.allSteppedToSame = allSteppedToSame
        self.setTemp = setTemp
        self.setRate = setRate
        self.setKi = setKi
        self.updateDataEveryMinute = updateDataEveryMinute
        self.timeSinceLastUpdate = timeSinceLastUpdate

# Custom exceptions for the system class
# This one is pretty much just when the thermocouple connection is lost
class SystemUnreliableError(Exception):
    """Raised when a system cannot be trusted, most likely when its thermocouple isn't connected.
    This is fatal and the program should shut down."""
    def __init__(self, systemID : int, elapsedTime : float, cause : str="unknown"):
        self.systemID = systemID
        self.elapsedTime = elapsedTime
        self.cause = cause
    
    def __str__(self):
        return "System {} became unreliable at elapsed time {} due to {}.".format(self.systemID, self.elapsedTime, 
                                                                         self.cause)

# This one is pretty much just when the thermocouples are working but the SSRs appear to not be working
class SystemInoperableError(Exception):
    """Raised when a system is inoperable, most likely when its SSR is broken. The system's data
    can still be trusted but it should not be allowed to act i.e. turn on its SSR."""
    def __init__(self, systemID : int, elapsedTime : float, cause : str="unknown"):
        self.systemID = systemID
        self.elapsedTime = elapsedTime
        self.cause = cause
    
    def __str__(self):
        return "System {} became inoperable at elapsed time {} due to {}.".format(self.systemID, self.elapsedTime,
                                                                          self.cause)

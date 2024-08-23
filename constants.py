from enum import IntEnum

SAVE_TO_FOLDER_STR = "./plots_data"

KP = 0
KD = 0
KI_SCALING_FACTOR = 10**-2
SET_PERIOD = 1.0 # in seconds; the effective period will be this + how long it takes to update the gui (usually 0.4s)
DELAY = 0.05 # in seconds; time for the pi to write to and read from the max6675 registers
TIME_TO_UPDATE_THE_UI_IF_NOT_EVERY_ITERATION = 60 # in seconds

TOTAL_STARTUP_TIME = 5  # in seconds
LARGE_TEMP_DIFFERENCE = 3   # degrees Celsius
MAX_TIME_AT_UNACCEPTABLE_TEMP = 0.5   # minutes, shut down all SSRs if the temperature is too off for this long
UNACCEPTABLE_TEMP_OVERSHOOT = 10   # degrees above the desired temperature, indicates potential SSR failure
MIN_ACCEPTABLE_TEMP = 15    # degrees, if continually reading a temp like this something is wrong with the
                            # temperature detector or the environment so shut off

MAX_SET_TEMP = 250  # degrees Celsius
MIN_SET_TEMP = 25  # degrees Celsius
MAX_SET_RATE = 5 # degrees Celsius per minute
MIN_SET_RATE = 0.1 # degrees Celsius per minute
MAX_SET_KI = 100
MIN_SET_KI = 1
STARTING_NUM_POINTS = 20
MAX_POINTS_IN_MEMORY = 1500
TIME_BETWEEN_ITERATIONS = 10    # milliseconds

CURRENT_TEMP_STR = "Current temp: {:.2f} C"
CURRENT_RATE_STR = "Current rate: {:.2f} C/m"

SET_TEMP_STR = "Set temp: {:.2f} C"
SET_RATE_STR = "Set rate: {:.2f} C/m"
SET_KI_STR = "Set Ki: {:.2f}"

# GPIOs to avoid: 0, 1, 14, 15 since reserved for i2c and uart
class CLOCK_PINS(IntEnum):
    """These pins (BOARD) on the pi will control the clock signal for SPI communication with the MAX6675. Any GPIO
    pins can be used for this regardless of pull up/down resistors since the clock signal is created by the pi raising and 
    lowering the pin voltage repeatedly."""
    CLK1 = 21 # gpio 9
    CLK2 = 24 # gpio 8
    CLK3 = 26 # gpio 7
    CLK4 = 31 # gpio 6

class DATA_PINS(IntEnum):
    """These pins (BOARD) on the pi will control the data signal for SPI communication with the MAX6675. Any GPIO
    pins can be used for this regardless of pull up/down resistors since this only matters if there is a clock signal
    which will not happen in the event of the pi crashing."""
    DATA1 = 19 # gpio 10
    DATA2 = 23 # gpio 11
    DATA3 = 32 # gpio 12
    DATA4 = 33 # gpio 13

# TODO: change the relay pins to be >= 9 and the chip selects ones to be < 9
# These pins on the pi will control which rtd to read data in from serially
class CHIP_SELECT(IntEnum):
    """These pins (BOARD) on the pi will control which temperature detector to read data in from serially.
    These pins should be GPIO < 9 since those are on by default and chip select is active low for SPI.."""
    CS1 = 3 # gpio 2
    CS2 = 5 # gpio 3
    CS3 = 7 # gpio 4
    CS4 = 29 # gpio 5

# These pins on the pi will turn on each ssr in parallel for their respective duty cycles
class RELAY_SELECT(IntEnum):
    """These pins (BOARD) on the pi will control if each SSR is on or off. It's important that these
    are GPIO >= 9 because the ones < 9 are on by default (and so is gpio 15 apparently, found by testing)."""
    RS1 = 11 # gpio 17
    RS2 = 12 # gpio 18
    RS3 = 36 # gpio 16
    RS4 = 35 # gpio 19

# To be used with the duty cycle assignments
# Check statuses before turning on an SSR
class OPERATION_STATUSES(IntEnum):
    """The statuses that a bake system can be in. OPERABLE means that the system is good to turn on its SSR, INOPERABLE
    means it should not. ON_HOLD means that it can turn on its SSR but with caution."""
    OPERABLE = 0
    INOPERABLE = 1
    ON_HOLD = 2

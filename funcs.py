import constants

# Implementation of the discrete pid algorithm
# s_current: float, the current value of the variable being controlled
# s_desired: float, the value that you eventually want the controlled variable to reach
# prev_error: float, the difference in current and desired error on the previous iteration (0 for the first one)
# error_running_sum: float, the sum of all previous errors
# kp: float, the proportional constant
# ki: float, the integral constant
# kd: float, the derivative constant
def pid(s_current : float, s_desired : float, prev_error : float, error_running_sum : float, 
        kp : float, ki : float, kd : float) -> tuple[float, float]:
    """
    An implementation of the discrete PID algorithm. Returns the output and the current error.

    s_current: the current value of the variable being controlled
    s_desired: the value that you eventually want the controlled variable to reach
    prev_error: the difference in current and desired error on the previous iteration (0 for the first one)
    error_running_sum: the sum of all previous errors
    kp: the proportional constant
    ki: the integral constant
    kd: the derivative constant

    Returns the output of the algorithm (duty cycle proportion) and the current error.
    """
    output = 0
    
    err_current = (s_desired - s_current)
    proportional = kp * err_current

    derivative = kd * (err_current - prev_error)

    integral = ki * constants.KI_SCALING_FACTOR * (error_running_sum + err_current)

    output = proportional + integral + derivative
    return output, err_current

# helper function
def clamp(value, hi, lo):
    """
    A helper function. Restricts the value to the given range between hi and lo. Types are not
    specified to make it more general, but it is assumed that value, hi, and lo are all of the same type.
    """
    return max(lo, min(value, hi))

# helper function
def rolling_moving_window(l : list, loc : int, window_size : int) -> list:
    """
    Returns a slice of the list l, ending at loc (included), with the length of window_size.
    """
    if loc >= window_size:
        return l[loc - window_size : loc]
    else:
        s = len(l)
        return l[s - (window_size - loc) : s] + l[0 : loc]

# helper function
def average_rate_of_change(time_list : list, value_list : list) -> float:
    """
    Returns the average rate of change of the values in value_list with respect to the times in time_list.
    """
    if len(value_list) < 2:
        return 0
    rate = (value_list[-1] - value_list[0]) / (time_list[-1] - time_list[0])
    return rate

# helper function
def all_same(items : list) -> bool:
    """
    Returns True if all the items in the list are the same, False otherwise.
    """
    return len(set(items)) == 1
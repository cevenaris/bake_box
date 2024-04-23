#include <Arduino.h>
#include <Vector.h>
const int SS1=6, SS2=7, SS3=8, SS4=9, SS5=10;

float control_var[5] = {0.5, 0.4, 0.3, 0.2, 0.1};

class DelayObject {
  public:
    DelayObject(float delay, int object) : delay(delay), object(object) {}

    bool operator <(const DelayObject& other);
    bool operator ==(const DelayObject& other);

    static void swap(DelayObject& a, DelayObject& b);

    int output_object();
  private:
    float delay;
    int object;
};

void setup() {
  Serial.begin(9600);

  DelayObject a = DelayObject(control_var[0], SS1);
  DelayObject b = DelayObject(control_var[1], SS2);
  DelayObject c = DelayObject(control_var[2], SS3);
  DelayObject d = DelayObject(control_var[3], SS4);
  DelayObject e = DelayObject(control_var[4], SS5);

  DelayObject arr[5] = {a, e, b, d, c};
  insertion_sort(arr, 5);
  for (int i = 0; i < 5; i++)
  {
    Serial.println(arr[i].output_object());
  }
}

void loop() {
  // put your main code here, to run repeatedly:

}

bool DelayObject::operator<(const DelayObject &other) {
  return this->delay < other.delay;
}

bool DelayObject::operator==(const DelayObject &other) {
  return this->delay == other.delay;
}

int DelayObject::output_object() {
  return object;
}

void DelayObject::swap(DelayObject &a, DelayObject &b) {
  float tempDelay = a.delay;
  float tempObject = a.object;
  a.delay = b.delay;
  a.object = b.object;
  b.delay = tempDelay;
  b.object = tempObject;
}

void insertion_sort(DelayObject dolist[], int size) {
  int i, j, temp;
  for (i = 0; i < size; i++)
  {
    j = i;
    while (j > 0 && dolist[j] < dolist[j - 1])
    {
      DelayObject::swap(dolist[j - 1], dolist[j]);
      j--;
    }
  }
}

float clamp(float val, float lo, float hi) {
  if (val < lo)
    return lo;
  else if (val > hi)
    return hi;
  return val;
}

/*
Considers the vector to have converged when the last NUM_CONSECUTIVE_CLOSE_ELEMENTS are within
+ or - CLOSE_RANGE to CONVERGE_TO
*/
bool has_converged(Vector<float> a) {
  const int NUM_CONSECUTIVE_CLOSE_ELEMENTS = 5;
  const float CLOSE_RANGE = 0.01;
  const float CONVERGE_TO = 0.0;

  if (a.size() < NUM_CONSECUTIVE_CLOSE_ELEMENTS) {
    return false;
  }

  bool potentially_converged = true;
  for (int i = a.size() - 1; a.size() - i <= NUM_CONSECUTIVE_CLOSE_ELEMENTS && potentially_converged; i--) {
    potentially_converged = (a[i] >= CONVERGE_TO - CLOSE_RANGE && a[i] <= CONVERGE_TO + CLOSE_RANGE);
  }
  return potentially_converged;
}

float pid(float s_current, float s_desired, float prev_error, float error_running_sum, float kp, float ki, float kd) {
  float output;

  float err_current = s_desired - s_current;
  float proportional = kp * err_current;

  // may need to adjust if this is the very first iteration of the algorithm
  float derivative = kd * (err_current - prev_error);

  sum_prev_errors += err_current;
  float integral = ki * sum_prev_errors;
  
  
  output = proportional + integral + derivative;
  return output;
}

float measure_temp() {
  return 0.0f;
}

void SSR_on() {
  return;
}

void SSR_off() {
  return;
}

void duty_cycle_from_temp(float desired_temp, float period, float prev_error, float error_running_sum, float kp, float ki, float kd) {
  float current_temp = measure_temp();
  float output = pid(current_temp, desired_temp, prev_error, error_running_sum, kp, ki, kd);
  output = clamp(output, 0.0, 1.0);
  float duty_cycle = output * period;
  SSR_on();
  delay(duty_cycle);
  SSR_off();
}

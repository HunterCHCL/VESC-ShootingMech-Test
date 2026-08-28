#ifndef __VESC_H__
#define __VESC_H__

#include "can.h"
#include "cmsis_os.h"

#define VESC_CAN_PORT hcan1
#define VESC_CAN_FIFO CAN_RX_FIFO0

#define VESC_ID_MOTOR1  0x01	//L1
#define VESC_ID_MOTOR2  0x02	//R1
#define VESC_ID_MOTOR3  0x03	//L2
#define VESC_ID_MOTOR4  0x04	//R2
#define VESC_ID_MOTOR5  0x05	//L3
#define VESC_ID_MOTOR6  0x06	//R3

#define VESC_CTRL_LOOP_PERIOD 50 //ms

#define VESC_CTRL_MIN_ERPM 350.0f // erpm
#define VESC_BREAK_CURRENT 0.5f // A
#define VESC_ERPM_MAX_ERROR 100

typedef enum {
	CAN_PACKET_SET_DUTY = 0,
	CAN_PACKET_SET_CURRENT,
	CAN_PACKET_SET_CURRENT_BRAKE,
	CAN_PACKET_SET_RPM,
	CAN_PACKET_SET_POS,
	CAN_PACKET_SET_CURRENT_REL = 10,
	CAN_PACKET_SET_CURRENT_BRAKE_REL,
	CAN_PACKET_SET_CURRENT_HANDBRAKE,
	CAN_PACKET_SET_CURRENT_HANDBRAKE_REL,
} CAN_PACKET_ID;

typedef enum {
    CAN_PACKET_STATUS_1 = 9,  //ERPM, Current, Duty Cycle
    CAN_PACKET_STATUS_2=14, //Ah Used, Ah Charged
    CAN_PACKET_STATUS_3,    //Wh Used, Wh Charged
    CAN_PACKET_STATUS_4,    //Temp Fet, Temp Motor, Current In, PID position
    CAN_PACKET_STATUS_5=27, //Tachometer, Voltage In
    CAN_PACKET_STATUS_6=58, //ADC1, ADC2, ADC3, PPM
} CAN_PACKET_STATUS_ID;

typedef struct {
	volatile float erpm;
	volatile float current;
	volatile float duty;
	volatile float tachometer;
	volatile float prev_tacho;
	volatile float target_erpm;
} VESC_Status;

extern VESC_Status vesc1_status;
extern VESC_Status vesc2_status;
extern VESC_Status vesc3_status;
extern VESC_Status vesc4_status;
extern VESC_Status vesc5_status;
extern VESC_Status vesc6_status;

void VESC_Init(void);
void VESC_can_set_duty(uint8_t controller_id, float duty);
void VESC_can_set_current(uint8_t controller_id, float current);
void VESC_can_set_current_off_delay(uint8_t controller_id, float current, float off_delay);
void VESC_can_set_current_brake(uint8_t controller_id, float current);
void VESC_can_set_rpm(uint8_t controller_id, float rpm);
void VESC_can_set_pos(uint8_t controller_id, float pos);
void VESC_can_set_current_rel(uint8_t controller_id, float current_rel);
void VESC_can_set_current_rel_off_delay(uint8_t controller_id, float current_rel, float off_delay);
void VESC_can_set_current_brake_rel(uint8_t controller_id, float current_rel);
void VESC_can_set_handbrake(uint8_t controller_id, float current);
void VESC_can_set_handbrake_rel(uint8_t controller_id, float current_rel);

#endif /* __VESC_H__ */

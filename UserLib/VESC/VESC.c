#include "VESC.h"

VESC_Status vesc1_status;
VESC_Status vesc2_status;
VESC_Status vesc3_status;
VESC_Status vesc4_status;
VESC_Status vesc5_status;
VESC_Status vesc6_status;

void VESC_Init(void)
{
    CAN_FilterTypeDef sFilterConfig;
    
    sFilterConfig.FilterBank = 0;
    sFilterConfig.FilterMode = CAN_FILTERMODE_IDMASK;
    sFilterConfig.FilterScale = CAN_FILTERSCALE_32BIT;
    sFilterConfig.FilterIdHigh = 0x0000; 
    sFilterConfig.FilterIdLow = 0x0000;
    sFilterConfig.FilterMaskIdHigh = 0x0000;
    sFilterConfig.FilterMaskIdLow = 0x0000;
    sFilterConfig.FilterFIFOAssignment = VESC_CAN_FIFO;
    sFilterConfig.FilterActivation = ENABLE;
    sFilterConfig.SlaveStartFilterBank = 14;

    HAL_CAN_ConfigFilter(&VESC_CAN_PORT, &sFilterConfig);
}
uint8_t can_transmit_eid(uint32_t id, const uint8_t *data, uint32_t len) {
	CAN_TxHeaderTypeDef txHeader = {0};
	static uint32_t txMailbox=0;
	uint8_t times=0;
    txHeader.StdId = 0;
    txHeader.ExtId = id;
    txHeader.IDE = CAN_ID_EXT;
    txHeader.RTR = CAN_RTR_DATA;
    txHeader.DLC = len;
	while (HAL_CAN_GetTxMailboxesFreeLevel(&VESC_CAN_PORT) == 0)
    {                                                         
        osDelay(1);
        if (times++ >= 5)
        {
            times = 0;
            return 3;
        }
    }
	return HAL_CAN_AddTxMessage(&VESC_CAN_PORT, &txHeader, data, &txMailbox);
}

static void buffer_append_int16(uint8_t* buffer, int16_t number, int32_t *index) {
	buffer[(*index)++] = number >> 8;
	buffer[(*index)++] = number;
}

static void buffer_append_int32(uint8_t* buffer, int32_t number, int32_t *index) {
	buffer[(*index)++] = number >> 24;
	buffer[(*index)++] = number >> 16;
	buffer[(*index)++] = number >> 8;
	buffer[(*index)++] = number;
}

static void buffer_append_float16(uint8_t* buffer, float number, float scale, int32_t *index) {
    buffer_append_int16(buffer, (int16_t)(number * scale), index);
}

static void buffer_append_float32(uint8_t* buffer, float number, float scale, int32_t *index) {
    buffer_append_int32(buffer, (int32_t)(number * scale), index);
}

void VESC_can_set_duty(uint8_t controller_id, float duty) {
	int32_t send_index = 0;
	uint8_t buffer[4];
	buffer_append_int32(buffer, (int32_t)(duty * 100000.0f), &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_DUTY << 8), buffer, send_index);
}

void VESC_can_set_current(uint8_t controller_id, float current) {
	int32_t send_index = 0;
	uint8_t buffer[4];
	buffer_append_int32(buffer, (int32_t)(current * 1000.0f), &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_CURRENT << 8), buffer, send_index);
}

void VESC_can_set_current_off_delay(uint8_t controller_id, float current, float off_delay) {
	int32_t send_index = 0;
	uint8_t buffer[6];
	buffer_append_int32(buffer, (int32_t)(current * 1000.0f), &send_index);
	buffer_append_float16(buffer, off_delay, 1e3f, &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_CURRENT << 8), buffer, send_index);
}

void VESC_can_set_current_brake(uint8_t controller_id, float current) {
	int32_t send_index = 0;
	uint8_t buffer[4];
	buffer_append_int32(buffer, (int32_t)(current * 1000.0f), &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_CURRENT_BRAKE << 8), buffer, send_index);
}

void VESC_can_set_rpm(uint8_t controller_id, float rpm) {
	int32_t send_index = 0;
	uint8_t buffer[4];
	buffer_append_int32(buffer, (int32_t)rpm, &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_RPM << 8), buffer, send_index);
}

void VESC_can_set_pos(uint8_t controller_id, float pos) {
	int32_t send_index = 0;
	uint8_t buffer[4];
	buffer_append_int32(buffer, (int32_t)(pos * 1000000.0f), &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_POS << 8), buffer, send_index);
}

void VESC_can_set_current_rel(uint8_t controller_id, float current_rel) {
	int32_t send_index = 0;
	uint8_t buffer[4];
	buffer_append_float32(buffer, current_rel, 1e5f, &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_CURRENT_REL << 8), buffer, send_index);
}

/**
 * Same as above, but also sets the off delay. Note that this command uses 6 bytes now. The off delay is useful to set to keep the current controller running for a while even after setting currents below the minimum current.
 */
void VESC_can_set_current_rel_off_delay(uint8_t controller_id, float current_rel, float off_delay) {
	int32_t send_index = 0;
	uint8_t buffer[6];
	buffer_append_float32(buffer, current_rel, 1e5f, &send_index);
	buffer_append_float16(buffer, off_delay, 1e3f, &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_CURRENT_REL << 8), buffer, send_index);
}

void VESC_can_set_current_brake_rel(uint8_t controller_id, float current_rel) {
	int32_t send_index = 0;
	uint8_t buffer[4];
	buffer_append_float32(buffer, current_rel, 1e5f, &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_CURRENT_BRAKE_REL << 8), buffer, send_index);
}

void VESC_can_set_handbrake(uint8_t controller_id, float current) {
	int32_t send_index = 0;
	uint8_t buffer[4];
	buffer_append_float32(buffer, current, 1e3f, &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_CURRENT_HANDBRAKE << 8), buffer, send_index);
}

void VESC_can_set_handbrake_rel(uint8_t controller_id, float current_rel) {
	int32_t send_index = 0;
	uint8_t buffer[4];
	buffer_append_float32(buffer, current_rel, 1e5f, &send_index);
	can_transmit_eid(controller_id |
			((uint32_t)CAN_PACKET_SET_CURRENT_HANDBRAKE_REL << 8), buffer, send_index);
}
//Recieve
static void VESC_process_status_1(uint8_t *data, VESC_Status *status) {
	status->erpm = (int32_t)(data[0] << 24 | data[1] << 16 | data[2] << 8 | data[3]);	//RPM
	status->current = ((int16_t)(data[4] << 8 | data[5])) / 10.0f;						//A
	status->duty = ((int16_t)(data[6] << 8 | data[7])) / 1000.0f;						//%/100
}

/*
void VESC_process_status_4(uint8_t *data, VESC_Status *status) {
	status->temp_fet = ((int16_t)(data[0] << 8 | data[1])) / 10.0f;		//DegC
	status->temp_motor = ((int16_t)(data[2] << 8 | data[3])) / 10.0f;	//DegC
	status->current_in = ((int16_t)(data[4] << 8 | data[5])) / 10.0f;	//A
	status->pid_pos = ((int32_t)(data[6] << 24 | data[7] << 16 | data[8] << 8 | data[9]))/50.0f;	//Deg
}
	*/
void VESC_process_status_5(uint8_t *data, VESC_Status *status) {
	status->tachometer = ((int32_t)(data[0] << 24 | data[1] << 16 | data[2] << 8 | data[3]))/6.0f;	//EREV
	//status->voltage_in = ((int16_t)(data[4] << 8 | data[5])) / 10.0f;	//V
}

void VESC_can_read_status(uint32_t *id,uint8_t *Data, VESC_Status *vesc_status) {
	uint8_t cmd = (uint8_t)((*id >> 8) & 0xFF);
	switch(cmd) {
		case CAN_PACKET_STATUS_1:
			VESC_process_status_1(Data, vesc_status);
			break;
		// case CAN_PACKET_STATUS_2:
		// 	VESC_process_status_2(Data, vesc_status);
		// 	break;
		// case CAN_PACKET_STATUS_3:
		// 	VESC_process_status_3(Data, vesc_status);
		// 	break;
		// case CAN_PACKET_STATUS_4:
		// 	VESC_process_status_4(Data, vesc_status);
		// 	break;
		case CAN_PACKET_STATUS_5:
			VESC_process_status_5(Data, vesc_status);
			break;
		default:
			break;
	}
}
void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan)
{
    uint8_t rxData[8] = {0};
    CAN_RxHeaderTypeDef rxHeader = {0};
	if (HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0, &rxHeader, rxData) != HAL_OK) {
		return;
	}
	if (rxHeader.IDE != CAN_ID_EXT || rxHeader.DLC < 8U) {
		return;
	}
	switch((uint8_t)(rxHeader.ExtId & 0xFF)) {
		case VESC_ID_MOTOR1:
			VESC_can_read_status(&rxHeader.ExtId, rxData, &vesc1_status);
			break;
		case VESC_ID_MOTOR2:
			VESC_can_read_status(&rxHeader.ExtId, rxData, &vesc2_status);
			break;
		case VESC_ID_MOTOR3:
			VESC_can_read_status(&rxHeader.ExtId, rxData, &vesc3_status);
			break;
		case VESC_ID_MOTOR4:
			VESC_can_read_status(&rxHeader.ExtId, rxData, &vesc4_status);
			break;
		case VESC_ID_MOTOR5:
			VESC_can_read_status(&rxHeader.ExtId, rxData, &vesc5_status);
			break;
		default:
			break;
	}
}

void VESC_HALT(void)
{
	VESC_can_set_rpm(VESC_ID_MOTOR1, 0);
	VESC_can_set_rpm(VESC_ID_MOTOR2, 0);
	VESC_can_set_rpm(VESC_ID_MOTOR3, 0);
	VESC_can_set_rpm(VESC_ID_MOTOR4, 0);
	VESC_can_set_rpm(VESC_ID_MOTOR5, 0);
	VESC_can_set_rpm(VESC_ID_MOTOR6, 0);
	VESC_can_set_current_brake(VESC_ID_MOTOR1, VESC_BREAK_CURRENT);
	VESC_can_set_current_brake(VESC_ID_MOTOR2, VESC_BREAK_CURRENT);
	VESC_can_set_current_brake(VESC_ID_MOTOR3, VESC_BREAK_CURRENT);
	VESC_can_set_current_brake(VESC_ID_MOTOR4, VESC_BREAK_CURRENT);
	VESC_can_set_current_brake(VESC_ID_MOTOR5, VESC_BREAK_CURRENT);
	VESC_can_set_current_brake(VESC_ID_MOTOR6, VESC_BREAK_CURRENT);
}

void VESC_ERPM_Ctrl(uint8_t VESC_ID,VESC_Status *vesc_status)
{
	float erpm;
	float target_erpm;

	taskENTER_CRITICAL();
	erpm = vesc_status->erpm;
	target_erpm = vesc_status->target_erpm;
	taskEXIT_CRITICAL();

	if(fabsf(erpm-target_erpm)>=VESC_ERPM_MAX_ERROR)
	{
		VESC_can_set_rpm(VESC_ID, target_erpm);
	}
	else
	{
		VESC_can_set_current_brake(VESC_ID, VESC_BREAK_CURRENT);
	}
}

// void VESC_Break(uint8_t VESC_ID,VESC_Status *vesc_status)
// {
// 	if(fabsf(vesc_status->erpm-VESC_CTRL_MIN_ERPM)>=VESC_ERPM_MAX_ERROR)
// 	{
// 		VESC_can_set_current_brake(VESC_ID,VESC_BREAK_CURRENT);
// 	}
// 	else
// 	{

// 	}
// }

void VESCCtrlTask(void *argument)
{
	/* USER CODE BEGIN MotorCtrlTask */
	VESC_Init();
	for(;;)
	{
		VESC_ERPM_Ctrl(VESC_ID_MOTOR1,&vesc1_status);
		VESC_ERPM_Ctrl(VESC_ID_MOTOR2,&vesc2_status);
		VESC_ERPM_Ctrl(VESC_ID_MOTOR3,&vesc3_status);
		VESC_ERPM_Ctrl(VESC_ID_MOTOR4,&vesc4_status);
		VESC_ERPM_Ctrl(VESC_ID_MOTOR5,&vesc5_status);
		VESC_ERPM_Ctrl(VESC_ID_MOTOR6,&vesc6_status);

		osDelay(VESC_CTRL_LOOP_PERIOD);
	}
	/* USER CODE END MotorCtrlTask */
}

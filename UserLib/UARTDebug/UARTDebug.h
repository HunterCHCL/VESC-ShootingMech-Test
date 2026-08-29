#ifndef __UARTDEBUG_H__
#define __UARTDEBUG_H__

#include "VESC.h"

#define UARTDebug_PORT huart1

#define UARTDebug_FRAME_HEAD1 0xFA
#define UARTDebug_FRAME_HEAD2 0xAF
#define UARTDebug_FRAME_MAX_LEN 64
#define UARTDEBUG_WATCHDOG_PERIOD 1000 //ms
#define UARTDEBUG_PERIOD 20 //ms

//ERROR Codes
#define UARTDEBUG_CHECKSUM_VALID 1
#define UARTDEBUG_CHECKSUM_INVALID 0

#define UARTDEBUG_ERR_NONE 0
#define UARTDEBUG_ERR_NOT_ENOUGH_DATA 1
#define UARTDEBUG_ERR_INVALID_FRAME_HEADER 2
#define UARTDEBUG_ERR_INVALID_CHECKSUM 3

//Command Codes
#define UARTDEBUG_CMD_VESC_UPDATE 0x01

typedef enum{
    DIRECT_CTRL,    
} UARTDebug_CtrlMode_t;
extern UARTDebug_CtrlMode_t UARTDebug_ctrl_mode;


#endif //__UARTDEBUG_H__

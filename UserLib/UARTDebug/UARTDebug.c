#include "usart.h"
#include "UARTDebug.h"

UARTDebug_CtrlMode_t UARTDebug_ctrl_mode = DIRECT_CTRL;

static uint8_t UARTDebug_RxBuffer[UARTDebug_FRAME_MAX_LEN];
static uint8_t UARTDebug_RxData[UARTDebug_FRAME_MAX_LEN];
static uint8_t UARTDebug_Rxcmd;
static volatile uint32_t UARTDebug_last_cmd_time = 0;

void UARTDebug_Init(void)
{
    HAL_UARTEx_ReceiveToIdle_DMA(&UARTDebug_PORT, UARTDebug_RxBuffer, UARTDebug_FRAME_MAX_LEN);
}

static void UARTDebug_SendData(uint8_t *data, uint16_t len)
{
    HAL_UART_Transmit_DMA(&UARTDebug_PORT, data, len);
}

static uint8_t UARTDebug_CheckSum(uint8_t *data, uint16_t len)
{
    uint8_t sum = 0;
    for (uint16_t i = 0; i < len - 1; i++) {
        sum += data[i];
    }
    if (sum == data[len - 1]) {
        return UARTDEBUG_CHECKSUM_VALID; // Checksum is valid
    } else {
        return UARTDEBUG_CHECKSUM_INVALID; // Checksum is invalid
    }
}

void UARTDebug_SendFrame(uint8_t *data, uint16_t len)
{
    // 帧结构：[H1][H2][data(len)][checksum]，共 len + 3 字节
    if (len > UARTDebug_FRAME_MAX_LEN - 3) {
        return;
    }
    uint8_t frame[UARTDebug_FRAME_MAX_LEN];
    frame[0] = UARTDebug_FRAME_HEAD1;
    frame[1] = UARTDebug_FRAME_HEAD2;
    memcpy(&frame[2], data, len);
    frame[len + 2] = 0; // Initialize checksum
    for (uint16_t i = 0; i < len + 2; i++) {
        frame[len + 2] += frame[i];
    }
    UARTDebug_SendData(frame, len + 3);
}

uint8_t UARTDebug_ProcessReceivedData(uint8_t *cmd,uint8_t *data,uint8_t *rx_data, uint16_t len)
{
    // 最小合法帧：[H1][H2][cmd][checksum] = 4 字节（空 payload）
    if (len < 4) {
        return UARTDEBUG_ERR_NOT_ENOUGH_DATA; // Not enough data for a valid frame
    }
    if (rx_data[0] != UARTDebug_FRAME_HEAD1 || rx_data[1] != UARTDebug_FRAME_HEAD2) {
        return UARTDEBUG_ERR_INVALID_FRAME_HEADER; // Invalid frame header
    }
    if (UARTDebug_CheckSum(rx_data, len)!=UARTDEBUG_CHECKSUM_VALID) {
        return UARTDEBUG_ERR_INVALID_CHECKSUM; // Invalid checksum
    }
    *cmd = rx_data[2]; // Extract the command
    memcpy(data, &rx_data[3], len - 4); // Extract the data（len-4：头2 + cmd1 + 校验1）
    return UARTDEBUG_ERR_NONE; // Success
}

void UARTDebug_UpdateVESC(uint8_t *data)
{
    UARTDebug_last_cmd_time = HAL_GetTick();
    memcpy(&vesc1_status.target_erpm, data, sizeof(float));
    memcpy(&vesc2_status.target_erpm, data + sizeof(float), sizeof(float));
    memcpy(&vesc3_status.target_erpm, data + 2 * sizeof(float), sizeof(float));
    memcpy(&vesc4_status.target_erpm, data + 3 * sizeof(float), sizeof(float));
    memcpy(&vesc5_status.target_erpm, data + 4 * sizeof(float), sizeof(float));
    memcpy(&vesc6_status.target_erpm, data + 5 * sizeof(float), sizeof(float));
}

void UARTDebug_SendVESCStatus(void)
{
    uint8_t data[6 * sizeof(float)];
    taskENTER_CRITICAL();
    memcpy(data, &vesc1_status.erpm, sizeof(float));
    memcpy(data + sizeof(float), &vesc2_status.erpm, sizeof(float));
    memcpy(data + 2 * sizeof(float), &vesc3_status.erpm, sizeof(float));
    memcpy(data + 3 * sizeof(float), &vesc4_status.erpm, sizeof(float));
    memcpy(data + 4 * sizeof(float), &vesc5_status.erpm, sizeof(float));
    memcpy(data + 5 * sizeof(float), &vesc6_status.erpm, sizeof(float));
    taskEXIT_CRITICAL();
    UARTDebug_SendFrame(data, sizeof(data));
}

void UARTDebug_WatchDog(void)
{
    if ((HAL_GetTick() - UARTDebug_last_cmd_time) > UARTDEBUG_WATCHDOG_PERIOD)
    {
        vesc1_status.target_erpm = 0.0f;
        vesc2_status.target_erpm = 0.0f;
        vesc3_status.target_erpm = 0.0f;
        vesc4_status.target_erpm = 0.0f;
        vesc5_status.target_erpm = 0.0f;
        vesc6_status.target_erpm = 0.0f;
    }
    UARTDebug_SendVESCStatus();
}

void UARTDebugTask(void *argument)
{
    UARTDebug_Init();
    for(;;)
    {
        UARTDebug_WatchDog();
        osDelay(UARTDEBUG_PERIOD);
    }
}

void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t Size)
{
    if (huart->Instance == UARTDebug_PORT.Instance) {
        uint8_t result = UARTDebug_ProcessReceivedData(&UARTDebug_Rxcmd, UARTDebug_RxData, UARTDebug_RxBuffer, Size);
        if (result == UARTDEBUG_ERR_NONE) {
            if (UARTDebug_Rxcmd == UARTDEBUG_CMD_VESC_UPDATE) {
                UARTDebug_UpdateVESC(&UARTDebug_RxData[0]);
            }
        }
        HAL_UARTEx_ReceiveToIdle_DMA(&UARTDebug_PORT, UARTDebug_RxBuffer, UARTDebug_FRAME_MAX_LEN);
    }
}
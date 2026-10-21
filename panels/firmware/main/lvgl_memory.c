/* LVGL's memory in PSRAM. With the C library's malloc, every small allocation
 * (each object, style and label) went to internal RAM first, as ESP-IDF keeps
 * allocations under 16 kB internal; with the Home panel's five screens that left
 * about 17 kB, and ESP-Hosted's Wi-Fi buffers failed at start-up. Internal RAM
 * stays for Wi-Fi, DMA and the tasks' stacks (sdkconfig.defaults). */

#include "esp_heap_caps.h"
#include "lvgl.h"

#define WHERE (MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)

void lv_mem_init(void)
{
}

void lv_mem_deinit(void)
{
}

lv_mem_pool_t lv_mem_add_pool(void *mem, size_t bytes)
{
    LV_UNUSED(mem);
    LV_UNUSED(bytes);
    return NULL;
}

void lv_mem_remove_pool(lv_mem_pool_t pool)
{
    LV_UNUSED(pool);
}

void *lv_malloc_core(size_t size)
{
    return heap_caps_malloc(size, WHERE);
}

void *lv_realloc_core(void *p, size_t new_size)
{
    return heap_caps_realloc(p, new_size, WHERE);
}

void lv_free_core(void *p)
{
    heap_caps_free(p);
}

void lv_mem_monitor_core(lv_mem_monitor_t *mon_p)
{
    LV_UNUSED(mon_p);
}

lv_result_t lv_mem_test_core(void)
{
    return LV_RESULT_OK;
}

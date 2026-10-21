/* Small icons drawn as shapes in a draw event: a handful of triangles and
 * rectangles each, so cheap for LVGL. */

#include "icons.h"

#include <stdint.h>

static void triangle(lv_layer_t *layer, lv_color_t colour, float x1, float y1, float x2, float y2, float x3,
                     float y3)
{
    lv_draw_triangle_dsc_t dsc;
    lv_draw_triangle_dsc_init(&dsc);
    dsc.color = colour;
    dsc.p[0] = (lv_point_precise_t){x1, y1};
    dsc.p[1] = (lv_point_precise_t){x2, y2};
    dsc.p[2] = (lv_point_precise_t){x3, y3};
    lv_draw_triangle(layer, &dsc);
}

static void bar(lv_layer_t *layer, lv_color_t colour, int x1, int y1, int x2, int y2)
{
    lv_draw_rect_dsc_t dsc;
    lv_draw_rect_dsc_init(&dsc);
    dsc.bg_color = colour;
    dsc.radius = 2;
    lv_area_t area = {x1, y1, x2, y2};
    lv_draw_rect(layer, &dsc, &area);
}

static void draw(lv_event_t *event)
{
    lv_obj_t *obj = lv_event_get_target(event);
    lv_layer_t *layer = lv_event_get_layer(event);
    lv_area_t a;
    lv_obj_get_coords(obj, &a);
    float s = lv_area_get_width(&a), x = a.x1, y = a.y1;
    lv_color_t c = lv_obj_get_style_text_color(obj, 0);
    switch ((icon_t)(intptr_t)lv_obj_get_user_data(obj)) {
    case ICON_PLAY:
        triangle(layer, c, x + s * 0.22f, y + s * 0.12f, x + s * 0.22f, y + s * 0.88f, x + s * 0.9f, y + s * 0.5f);
        break;
    case ICON_PAUSE:
        bar(layer, c, x + s * 0.2f, y + s * 0.14f, x + s * 0.4f, y + s * 0.86f);
        bar(layer, c, x + s * 0.6f, y + s * 0.14f, x + s * 0.8f, y + s * 0.86f);
        break;
    case ICON_NEXT:
        triangle(layer, c, x + s * 0.12f, y + s * 0.16f, x + s * 0.12f, y + s * 0.84f, x + s * 0.72f, y + s * 0.5f);
        bar(layer, c, x + s * 0.74f, y + s * 0.16f, x + s * 0.88f, y + s * 0.84f);
        break;
    case ICON_PREVIOUS:
        triangle(layer, c, x + s * 0.88f, y + s * 0.16f, x + s * 0.88f, y + s * 0.84f, x + s * 0.28f, y + s * 0.5f);
        bar(layer, c, x + s * 0.12f, y + s * 0.16f, x + s * 0.26f, y + s * 0.84f);
        break;
    }
}

lv_obj_t *icon_create(lv_obj_t *parent, icon_t icon, int size, uint32_t colour)
{
    lv_obj_t *obj = lv_obj_create(parent);
    lv_obj_remove_style_all(obj);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE | LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_size(obj, size, size);
    lv_obj_set_style_text_color(obj, lv_color_hex(colour), 0);
    lv_obj_set_user_data(obj, (void *)(intptr_t)icon);
    lv_obj_add_event_cb(obj, draw, LV_EVENT_DRAW_MAIN, NULL);
    return obj;
}

void icon_set(lv_obj_t *obj, icon_t icon)
{
    if ((icon_t)(intptr_t)lv_obj_get_user_data(obj) != icon) {
        lv_obj_set_user_data(obj, (void *)(intptr_t)icon);
        lv_obj_invalidate(obj);
    }
}

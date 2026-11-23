/* The building blocks the panel screens share (ui.h). */

#include "ui.h"

#include "esp_heap_caps.h"
#include "tokens.h"

lv_obj_t *ui_plain(lv_obj_t *parent)
{
    lv_obj_t *obj = lv_obj_create(parent);
    lv_obj_remove_style_all(obj);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE | LV_OBJ_FLAG_CLICKABLE);
    return obj;
}

lv_obj_t *ui_text(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(colour), 0);
    lv_label_set_text(label, "");
    return label;
}

lv_obj_t *ui_one_line(lv_obj_t *parent, const lv_font_t *font, uint32_t colour, int32_t width)
{
    lv_obj_t *label = ui_text(parent, font, colour);
    lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
    lv_obj_set_size(label, width, lv_font_get_line_height(font));
    return label;
}

lv_obj_t *ui_pill(lv_obj_t *parent, const lv_font_t *font, lv_obj_t **text)
{
    lv_obj_t *pill = ui_plain(parent);
    lv_obj_set_size(pill, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(pill, 16, 0);
    lv_obj_set_style_pad_ver(pill, 3, 0);
    lv_obj_set_style_radius(pill, 20, 0);
    lv_obj_set_style_bg_opa(pill, 38, 0); /* about 15%, as the hub's tinted pills */
    *text = ui_text(pill, font, TOK_DESK_MUTED);
    lv_obj_set_style_text_letter_space(*text, 2, 0);
    return pill;
}

void ui_pill_tone(lv_obj_t *pill, lv_obj_t *text, uint32_t colour)
{
    lv_obj_set_style_bg_color(pill, lv_color_hex(colour), 0);
    lv_obj_set_style_text_color(text, lv_color_hex(colour), 0);
}

lv_obj_t *ui_cells(lv_obj_t *parent, int32_t x, int32_t y, int32_t width, int32_t height, int count,
                   lv_obj_t **cells)
{
    /* The box is the hairline colour; the cells cover it but for 2px between and round them. */
    lv_obj_t *box = ui_plain(parent);
    lv_obj_set_pos(box, x, y);
    lv_obj_set_size(box, width, height);
    lv_obj_set_style_radius(box, 20, 0);
    lv_obj_set_style_clip_corner(box, true, 0);
    lv_obj_set_style_bg_color(box, lv_color_hex(TOK_DESK_HAIRLINE), 0);
    lv_obj_set_style_bg_opa(box, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_all(box, 2, 0);
    lv_obj_set_style_pad_column(box, 2, 0);
    lv_obj_set_flex_flow(box, LV_FLEX_FLOW_ROW);
    for (int i = 0; i < count; i++) {
        cells[i] = ui_plain(box);
        lv_obj_set_height(cells[i], LV_PCT(100));
        lv_obj_set_flex_grow(cells[i], 1);
        lv_obj_set_style_bg_color(cells[i], lv_color_hex(TOK_DESK_CELL), 0);
        lv_obj_set_style_bg_opa(cells[i], LV_OPA_COVER, 0);
    }
    return box;
}

void ui_upper(char *to, size_t size, const char *from)
{
    size_t i = 0;
    for (; from[i] && i < size - 1; i++) {
        to[i] = (from[i] >= 'a' && from[i] <= 'z') ? from[i] - 32 : from[i];
    }
    to[i] = '\0';
}

void ui_take_picture(int slot, ui_picture_t *picture)
{
    picture_t fresh;
    if (!pictures_take(slot, &fresh)) {
        return;
    }
    picture_t old = picture->showing;
    picture->showing = fresh;
    if (fresh.pixels) {
        picture->dsc = (lv_image_dsc_t){
            .header = {.magic = LV_IMAGE_HEADER_MAGIC, .cf = LV_COLOR_FORMAT_RGB888, .w = fresh.width,
                       .h = fresh.height, .stride = fresh.width * 3},
            .data_size = fresh.width * fresh.height * 3,
            .data = fresh.pixels,
        };
        lv_image_set_src(picture->image, &picture->dsc);
        lv_image_cache_drop(&picture->dsc);
    } else {
        lv_image_set_src(picture->image, NULL);
    }
    lv_obj_set_flag(picture->image, LV_OBJ_FLAG_HIDDEN, fresh.pixels == NULL);
    heap_caps_free(old.pixels);
}

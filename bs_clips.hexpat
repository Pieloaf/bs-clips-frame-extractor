#pragma loop_limit 1000000
#include <zlib.hexpat>

import std.core;
import std.sys;
import std.string;
import std.mem;
import type.color;
import hex.dec;
import hex.core;

std::mem::Section clip_data = std::mem::create_section("clip_data");
std::mem::Section sheet_data = std::mem::create_section("sheet_data");
std::mem::Section image_data = std::mem::create_section("image_data");

// Decompress the clips file
auto clip_decomp = hex::dec::zlib_decompress(zlib,clip_data,15);

std::core::set_endian(1);

using string16 = std::string::SizedString<u16>;
using RGBA8 = type::RGBA<8,8,8,8>;

bitfield c_flags {
    bool isLooping: 1;
    bool hasSpritesheet: 1;
    bool isHighQuality: 1;
    bool isPNGEncoded: 1;
};

bitfield fs_flags {
    bool hasEvent: 1;
    bool hasChildren: 1;
    bool isLocomotive: 1;  
};

bitfield f_flags {
    bool hasOffset: 1;
    bool isShared: 1;
    bool hasChildren: 1;
    bool hasSheet: 1;
    bool isLocomotive: 1;
};

struct event {
    u16 n[[hidden]];
    char name[n];
    u16 frame_start;
};

struct offset {
    float x;
    float y;
};

struct buffer {
    u32 offset;
    s32 length;
};

struct size {
    u16 w;
    u16 h;
};

struct sheet {
    buffer buffer;
    size size;
};

struct bound {
    offset[[inline]];
    float w;
    float h;
};

struct frame {
    u16 frame_num;

    if (frame_num == std::core::array_index()){
        le f_flags frame_flags;
        if (frame_flags.isLocomotive) {
            u32 locomotive_tiles;
        }
        if (frame_flags.hasOffset){
            offset offset;
        }
        u16 origBmpNum;
        if (frame_flags.hasSheet){
            sheet f_sheet;
            std::mem::copy_value_to_section(f_sheet.buffer, sheet_data, origBmpNum*sizeof(buffer));
        }
        bound;
        if (frame_flags.hasChildren){
          //TODO
        }
    }
};

struct frame_seq {
    le fs_flags flags;
    if (flags.isLocomotive){
       u32 locomotive_tile_count;
    }
    if (flags.hasEvent){
        u8 event_count;
        event events[event_count];
    }
    if (flags.hasChildren){
     // TODO
    }
    
    u16 frame_count;
    frame frames[frame_count];
};

struct compressed_img {
    u8 data[image_placement[std::core::array_index()].length];
};

struct clip {
    string16 anim_id;
    string16 anim_url;
    le c_flags clip_flags;
    u16 frame_count;
    u8 frame_rate;
    frame_seq clip_frame_seq;
    u32 u_frames = std::mem::get_section_size(sheet_data)/sizeof(buffer);
    buffer image_placement[u_frames] @ 0x0 in sheet_data[[hidden]];
    compressed_img c_imgs[u_frames];
};

u16 selected_clip in;
u16 selected_frame in;

u16 w = 0;
u16 h = 0;

clip clips[selected_clip+1] @ 0 in clip_data;
u16 clip_i = selected_clip;
hex::dec::zlib_decompress(clips[clip_i].c_imgs[selected_frame],image_data,15);

for (u16 i = 0, i < clips[clip_i].frame_count, i+=1) {
    if (clips[clip_i].clip_frame_seq.frames[i].frame_num == i) { 
        if (clips[clip_i].clip_frame_seq.frames[i].origBmpNum == selected_frame) {
            w = clips[clip_i].clip_frame_seq.frames[i].f_sheet.size.w;
            h = clips[clip_i].clip_frame_seq.frames[i].f_sheet.size.h;
        }
    }
}

u32 size_in_bytes = std::mem::get_section_size(image_data);
u32 pixel_count = size_in_bytes / 4;

struct ARGB {
    u8 a;
    u8 r;
    u8 g;
    u8 b;
}[[hidden]];

ARGB argb[pixel_count] @ 0[[hidden]];

struct BGRA {
  u8 b @ addressof(argb[std::core::array_index()].r);
  u8 g @ addressof(argb[std::core::array_index()].g);
  u8 r @ addressof(argb[std::core::array_index()].b);
  u8 a @ addressof(argb[std::core::array_index()].a);
};

struct image {
  BGRA data[pixel_count] [[inline]];
}  [[hex::visualize("bitmap", data, w, h)]];


image bgra_image @ 0 in image_data;
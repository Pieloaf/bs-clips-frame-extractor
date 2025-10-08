from dataclasses import dataclass, field
import struct
import zlib
import os
from pathlib import Path
from PIL import Image

CLIPS_FILE = None
OUT_DIR = None

class ByteReader:
    def __init__(self, blob, pos):
        self.blob = blob
        self.pos = pos
        self.end = len(blob)

    def tell(self): return self.pos

    def seek(self, p):
        self.pos = max(min(p, self.end), 0)

    def _ensure(self, n):
        if self.pos + n > self.end:
            raise EOFError("read past end")

    def read_u8(self):
        self._ensure(1)
        v = self.blob[self.pos]
        self.pos += 1
        return v

    def read_u16(self):
        self._ensure(2)
        v = struct.unpack_from(">H", self.blob, self.pos)[0]
        self.pos += 2
        return v

    def read_s16(self):
        self._ensure(2)
        v = struct.unpack_from(">h", self.blob, self.pos)[0]
        self.pos += 2
        return v

    def read_u32(self):
        self._ensure(4)
        v = struct.unpack_from(">I", self.blob, self.pos)[0]
        self.pos += 4
        return v

    def read_s32(self):
        self._ensure(4)
        v = struct.unpack_from(">i", self.blob, self.pos)[0]
        self.pos += 4
        return v

    def read_f32(self):
        self._ensure(4)
        v = struct.unpack_from(">f", self.blob, self.pos)[0]
        self.pos += 4
        return v

    def read_utf(self):
        l = self.read_u16()
        self._ensure(l)
        s = self.blob[self.pos:self.pos+l].decode("utf-8", errors="replace")
        self.pos += l
        return s


@dataclass
class AnimFrame:
    frame_num: int = 0
    shared: int = 0
    shared_from: int = 0
    locomotive_tiles: float = 0
    offset: dict = field(default_factory=dict)  # TODO define Point(x,y)
    origBmpdNum: int = 0
    # TODO define Sheet(buf(offset, len), size(w, h))
    sheet: dict = field(default_factory=dict)
    bound: dict = field(default_factory=dict)  # TODO define Rect(x,y,w,h)
    children: list = field(default_factory=list)

    def readBytes(self, br: ByteReader, frameIndex: int):
        self.frame_num = br.read_s16()
        if self.frame_num != frameIndex:
            return

        flags = br.read_u8()
        has_offset = bool(flags & 1)
        self.shared = bool(flags & 2)
        has_children = bool(flags & 4)
        has_sheet = bool(flags & 8)
        has_locomotive = bool(flags & 0x10)

        if has_locomotive:
            self.locomotive_tiles = br.read_f32()
        if has_offset:
            self.offset = {
                "x": br.read_f32(),
                "y": br.read_f32()
            }
        self.origBmpdNum = br.read_u16()
        if self.shared:
            self.shared_from = br.read_u16()
        elif has_sheet:
            self.sheet = {
                "buffer": {
                    "offset": br.read_u32(),
                    "length": br.read_s32()
                },
                "size": {
                    "w": br.read_u16(),
                    "h": br.read_u16()
                }
            }

        self.bound = {
            "x": br.read_f32(),
            "y": br.read_f32(),
            "w": br.read_f32(),
            "h": br.read_f32()
        }

        # children
        if not has_children:
            return

        child_count = br.read_u8()
        for _ in range(child_count):
            # TODO AnimFrameChild class
            child_index = br.read_u8()
            frame_num = br.read_s16()

            if frame_num >= 0:
                return

            cflags = br.read_u8()
            child = {
                'childIndex': child_index,
                'frameNum': frame_num,
                'position':  (br.read_f32(), br.read_f32()) if cflags & 1 else None,
                'scale':  (br.read_f32(), br.read_f32()) if cflags & 2 else None,
                'rotation':  br.read_f32() if cflags & 4 else 0,
                'alpha':  br.read_f32() if cflags & 8 else 1,
                'blendMode':  br.read_utf() if cflags & 0x10 else None,
                'visible': bool(cflags & 0x20),
                'color': br.read_u32()if cflags & 0x40 else 0,
                'transformMatrix': (br.read_f32(), br.read_f32(
                ), br.read_f32(), br.read_f32(), br.read_f32(), br.read_f32()) if cflags & 0x80 else None
            }
            self.children.append(child)


@dataclass
class AnimFrames:
    clip_flags: int = 0

    events: list = field(default_factory=list)
    children: list = field(default_factory=list)
    frames: list = field(default_factory=list)

    has_events: bool = False
    has_children: bool = False

    locomotive: bool = False
    locomotiveTilesTotal: float = 0

    def readBytes(self, br: ByteReader):
        self.clip_flags = br.read_u8()
        self.has_events = bool(self.clip_flags & 1)
        self.has_children = bool(self.clip_flags & 2)
        self.locomotive = bool(self.clip_flags & 4)

        if self.locomotive:
            self.locomotive_tiles_total = br.read_f32()

        if self.has_events:
            eventCount = br.read_u8()
            for _ in range(eventCount):
                e = {
                    "event": br.read_utf(),
                    "frameNumber": br.read_u16()
                }
                self.events.append(e)

        if self.has_children:
            child_count = br.read_u8()
            for _ in range(child_count):
                cd = {
                    'url': br.read_utf(),
                    'name': br.read_utf(),
                    'className': br.read_utf(),
                    'index': br.read_u8(),
                    'front': bool(br.read_u8()),
                    'parentStartFrame': br.read_s16()
                }
                self.children.append(cd)

        frame_count = br.read_u16()
        if frame_count:
            for i in range(frame_count):
                try:
                    frame = AnimFrame()
                    frame.readBytes(br, i)
                    self.frames.append(frame)
                except:
                    pass

# TODO BROKEN CODE related to repeated and shared frames
    # if len(frames):
    #     for fi in range(len(frames)):
    #         f = frames[fi]
    #         if f["frameNum"] < 0:
    #             f["frameNum"] = fi
    #             if f.get("shared"):
    #                 src_idx = int(f.get("sharedFrom", -1))
    #                 if 0 <= src_idx < len(frames) and frames[src_idx]:
    #                     f["origBmpdNum"] = frames[src_idx].get("origBmpdNum")
    #                 else:
    #                     # mark unresolved so you can inspect later; don't crash
    #                     f["origBmpdNum"] = None
    #                     f.setdefault("notes", []).append(f"sharedFrom {src_idx} unresolved")
    #         elif f["frameNum"] != fi:
    #             ref = int(f["frameNum"])
    #             if 0 <= ref < len(frames) and frames[ref]:
    #                 frames[fi] = frames[ref]   # alias as in AS3
    #             else:
    #                 # invalid reference — log/mark instead of crashing
    #                 frames[fi] = None
    #                 # optionally collect errors in a list for debugging
    #                 f.setdefault("notes", []).append(f"INVALID frame {fi}: points to {ref}")


@dataclass
class AnimClip:
    id: str = ""
    url: str = ""

    # Clip options
    scale: float = 0
    offset_x: float = 0
    offset_y: float = 0
    shruken_scale: float = 0

    frame_count: int = 0
    frame_rate: int = 0
    flags: dict = field(default_factory=dict)

    frame_data: AnimFrames = None

    def readBytes(self, br: ByteReader):
        # parse header
        self.id = br.read_utf()
        self.url = br.read_utf()
        print(f"Found Clip: {self.id} ({self.url}) at {hex(br.tell())}")
        options = br.read_u8()
        self.frame_count = br.read_u16()
        self.frame_rate = br.read_u8()

        if options & 0x10:
            self.scale = br.read_f32()
        if options & 0x20:
            self.offset_x = br.read_f32()
        if options & 0x40:
            self.offset_y = br.read_f32()
        if options & 0x80:
            self.shrunken_scale = br.read_f32()

        self.flags = {
            "isLooping": bool(options & 1) or ".portrait/" in self.url,
            "hasSpriteSheet": bool(options & 2),
            "isHighQuality": bool(options & 4),
            "isPngEncoded": bool(options & 8),
        }

        self.frame_data = AnimFrames()
        self.frame_data.readBytes(br)


def decompressFrames(br: ByteReader, anim_id: str, frames: list[AnimFrame]):
    base_offset = br.tell()
    for fi, f in enumerate(frames):
        if not f.sheet:
            continue

        # Get the compressed data
        buf_start = base_offset + f.sheet["buffer"]["offset"]
        buf_end = buf_start + f.sheet["buffer"]["length"]
        imgData = zlib.decompress(data[buf_start:buf_end])

        # Get dimensions
        width = f.sheet["size"]["w"]
        height = f.sheet["size"]["h"]

        try:
            rgba_data = bytearray(len(imgData))
            for i in range(0, len(imgData), 4):
                a, r, g, b = imgData[i:i+4]  # ARGB format
                # Convert to RGBA for PIL
                rgba_data[i:i+4] = bytes([r, g, b, a])

            # Create image from bytes
            img = Image.frombytes('RGBA', (width, height), rgba_data)

            # Save as PNG
            os.makedirs(f"{OUT_DIR}/{anim_id}", exist_ok=True)
            outname = f"{OUT_DIR}/{anim_id}/{fi:03d}.png"
            img.save(outname)
            br.seek(buf_end)
        except Exception as e:
            print(f"Failed to convert frame {anim_id}/{fi}: {e}")

# MAIN
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input_file> <output_dir>")
        sys.exit(1)

    CLIPS_FILE = sys.argv[1]
    OUT_DIR = Path(sys.argv[2])
    OUT_DIR = OUT_DIR / CLIPS_FILE.split("/")[-1]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    data = None
    with open(CLIPS_FILE, "rb") as cf:
        cf_compressed = cf.read()
        data = zlib.decompress(cf_compressed)

    br = ByteReader(data, 0)
    while br.tell() < len(data):
        parsed_clip = AnimClip()
        parsed_clip.readBytes(br)
        print(f"Parsed Clip: {parsed_clip.id} | frames: {len(parsed_clip.frame_data.frames)}")
        decompressFrames(br, parsed_clip.id, parsed_clip.frame_data.frames)
        print(f"Decompressed frames for {parsed_clip.id}. Output in {OUT_DIR}/{parsed_clip.id}/")

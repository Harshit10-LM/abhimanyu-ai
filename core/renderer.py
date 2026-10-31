"""Digital twin visualizer and hardware pin state renderer using Pillow.

Renders board graphics with live glowing LED indicators, logic level badges,
PWM duty cycle bars, and timing waveforms.
"""

import math
import os
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from core.board_database import BoardSpec
from core.schemas import PinSnapshot, SimulationFrame, SimulationPlan

COLOR_BG = (13, 17, 23)
COLOR_PANEL_BG = (22, 27, 34)
COLOR_BORDER = (48, 54, 61)
COLOR_TEXT = (230, 237, 243)
COLOR_TEXT_MUTED = (139, 148, 158)
COLOR_CYAN = (0, 210, 255)
COLOR_GREEN_GLOW = (57, 211, 83)
COLOR_RED_GLOW = (255, 69, 58)
COLOR_DARK_OFF = (33, 38, 45)
COLOR_UNKNOWN = (210, 153, 34)


class HardwareRenderer:
    """Renders virtual microcontroller hardware frames and pin waveforms."""

    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = assets_dir

    def render_frame(
        self,
        board: BoardSpec,
        frame: SimulationFrame,
        plan: SimulationPlan,
        width: int = 900,
        height: int = 560,
    ) -> Image.Image:
        """Renders a comprehensive hardware digital twin view for the given frame."""
        canvas = Image.new("RGB", (width, height), color=COLOR_BG)
        draw = ImageDraw.Draw(canvas)

        # 1. Top Header Banner: Time & Event
        draw.rectangle([0, 0, width, 60], fill=COLOR_PANEL_BG)
        draw.line([(0, 60), (width, 60)], fill=COLOR_BORDER, width=2)

        time_str = f"SIMULATION TIME: {frame.t_ms} ms"
        draw.text((20, 18), time_str, fill=COLOR_CYAN)

        evt_str = frame.active_event_description or "System running"
        # Truncate if long
        if len(evt_str) > 75:
            evt_str = evt_str[:72] + "..."
        draw.text((320, 18), f"ACTIVE EVENT: {evt_str}", fill=COLOR_TEXT)

        # 2. Board Graphic (Left half or central area)
        board_img_path = os.path.join(self.assets_dir, "boards", f"{board.id}.png")
        if os.path.exists(board_img_path):
            try:
                base_board = Image.open(board_img_path).convert("RGBA")
                base_board = base_board.resize((480, 310), Image.Resampling.LANCZOS)
                canvas.paste(base_board, (20, 80))
            except Exception:
                self._draw_fallback_board_rect(draw, 20, 80, 480, 310, board)
        else:
            self._draw_fallback_board_rect(draw, 20, 80, 480, 310, board)

        # Board Title Overlay
        draw.text((30, 90), f"{board.display_name.upper()}", fill=(255, 255, 255))
        draw.text((30, 110), f"Logic: {board.logic_voltage}V | {board.mcu}", fill=COLOR_TEXT_MUTED)

        # 3. Right Pin State Inspector Panel
        panel_x = 520
        panel_w = width - panel_x - 20
        draw.rounded_rectangle(
            [panel_x, 80, panel_x + panel_w, height - 20],
            radius=8,
            fill=COLOR_PANEL_BG,
            outline=COLOR_BORDER,
            width=2,
        )

        draw.text((panel_x + 16, 95), "ACTIVE PIN STATES", fill=COLOR_CYAN)
        draw.line(
            [(panel_x + 16, 120), (panel_x + panel_w - 16, 120)],
            fill=COLOR_BORDER,
            width=1,
        )

        # Render pin items
        row_y = 135
        sorted_pins = sorted(
            frame.pin_states.values(),
            key=lambda p: (0 if "OUT" in p.mode.upper() else 1, p.pin),
        )

        if not sorted_pins:
            draw.text(
                (panel_x + 20, row_y),
                "No pins configured in firmware.",
                fill=COLOR_TEXT_MUTED,
            )
        else:
            for pin_snap in sorted_pins[:9]:  # display up to 9 active pins
                self._render_pin_row(draw, panel_x + 16, row_y, panel_w - 32, pin_snap)
                row_y += 44

        # 4. Bottom Microcontroller Output / LED Indicator
        output_snaps = [
            s for s in frame.pin_states.values()
            if "OUT" in s.mode.upper()
        ]
        default_onboard = (
            "13" if board.id == "arduino_uno" else ("2" if board.id == "esp32_devkit" else "PC13")
        )

        target_snap = None
        for s in output_snaps:
            if s.digital_state == "HIGH" or (s.component_hint and "LED" in s.component_hint.upper()):
                target_snap = s
                break
        if not target_snap and output_snaps:
            target_snap = output_snaps[0]
        if not target_snap:
            target_snap = frame.pin_states.get(default_onboard)

        active_pin_name = target_snap.pin if target_snap else default_onboard
        is_lit = False
        if target_snap:
            if board.id == "stm32_bluepill" and target_snap.pin == "PC13":
                is_lit = target_snap.digital_state == "LOW"
            else:
                is_lit = target_snap.digital_state == "HIGH"

        self._render_onboard_led_widget(
            draw, 50, 415, active_pin_name, is_lit, board, target_snap, output_snaps
        )

        return canvas

    def _draw_fallback_board_rect(
        self, draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, board: BoardSpec
    ) -> None:
        """Draws schematic fallback rectangle if board PNG is missing."""
        draw.rounded_rectangle(
            [x, y, x + w, y + h],
            radius=12,
            fill=(20, 35, 55),
            outline=COLOR_CYAN,
            width=2,
        )
        draw.text((x + 20, y + 20), board.display_name, fill=COLOR_TEXT)

    def _render_pin_row(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        w: int,
        snap: PinSnapshot,
    ) -> None:
        """Draws a single pin state row in the inspector panel."""
        # Background card
        draw.rounded_rectangle(
            [x, y, x + w, y + 36],
            radius=4,
            fill=(18, 22, 28),
            outline=(35, 42, 52),
            width=1,
        )

        # Pin Identifier Badge
        pin_label = f"PIN {snap.pin}"
        draw.text((x + 10, y + 10), pin_label, fill=COLOR_TEXT)

        # Mode hint
        mode_text = snap.mode
        if snap.component_hint:
            mode_text += f" ({snap.component_hint})"
        draw.text((x + 85, y + 10), mode_text[:16], fill=COLOR_TEXT_MUTED)

        # Value Indicator & LED
        state = snap.digital_state
        indicator_x = x + w - 75

        if state == "HIGH":
            # Glow circle
            draw.ellipse(
                [indicator_x, y + 10, indicator_x + 16, y + 26],
                fill=COLOR_RED_GLOW,
                outline=(255, 180, 180),
                width=1,
            )
            draw.text((indicator_x + 24, y + 10), "HIGH", fill=COLOR_RED_GLOW)
        elif state == "LOW":
            draw.ellipse(
                [indicator_x, y + 10, indicator_x + 16, y + 26],
                fill=COLOR_DARK_OFF,
                outline=(60, 70, 80),
                width=1,
            )
            draw.text((indicator_x + 24, y + 10), "LOW", fill=COLOR_TEXT_MUTED)
        else:
            draw.ellipse(
                [indicator_x, y + 10, indicator_x + 16, y + 26],
                fill=COLOR_UNKNOWN,
                outline=(255, 220, 100),
                width=1,
            )
            draw.text((indicator_x + 24, y + 10), "UNK", fill=COLOR_UNKNOWN)

        # PWM Duty Cycle bar if analogWrite active
        if snap.pwm_duty is not None and snap.pwm_duty > 0 and snap.pwm_duty < 255:
            bar_w = 40
            filled_w = int((snap.pwm_duty / 255.0) * bar_w)
            bx = indicator_x - 50
            draw.rectangle([bx, y + 14, bx + bar_w, y + 22], fill=(40, 45, 50))
            draw.rectangle([bx, y + 14, bx + filled_w, y + 22], fill=COLOR_CYAN)

        # Analog ADC display if analogRead active
        elif snap.analog_value is not None:
            draw.text((indicator_x - 65, y + 10), f"ADC:{snap.analog_value}", fill=COLOR_CYAN)

    def _render_onboard_led_widget(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        pin_name: str,
        is_lit: bool,
        board: BoardSpec,
        target_snap: Optional[PinSnapshot] = None,
        output_snaps: Optional[List[PinSnapshot]] = None,
    ) -> None:
        """Draws visual glowing LED indicator for the active output pin / diagnostic LED."""
        draw.rounded_rectangle(
            [x, y, x + 420, y + 100],
            radius=8,
            fill=COLOR_PANEL_BG,
            outline=COLOR_BORDER,
            width=2,
        )

        title_hint = f"Pin {pin_name}"
        if target_snap and target_snap.component_hint:
            title_hint += f" ({target_snap.component_hint})"
        draw.text(
            (x + 16, y + 14),
            f"VIRTUAL OUTPUT ACTUATOR: {title_hint}",
            fill=COLOR_TEXT,
        )

        status_text = "STATE: HIGH / ENERGIZED" if is_lit else "STATE: LOW / OFF"
        if board.id == "stm32_bluepill" and pin_name == "PC13":
            status_text += " [Active Low]"
        status_color = COLOR_GREEN_GLOW if is_lit else COLOR_TEXT_MUTED
        draw.text((x + 16, y + 36), status_text, fill=status_color)

        # Show other output pin badges if multiple outputs exist
        if output_snaps and len(output_snaps) > 1:
            other_text = "Other Outputs: " + ", ".join(
                f"{p.pin}:{'H' if p.digital_state=='HIGH' else 'L'}"
                for p in output_snaps[:4]
                if p.pin != pin_name
            )
            draw.text((x + 16, y + 65), other_text[:40], fill=COLOR_CYAN)

        # LED Graphic Bulb
        bulb_cx = x + 350
        bulb_cy = y + 50
        radius = 24

        if is_lit:
            # Outer diffuse glow
            for r, alpha_color in [(36, (20, 80, 30)), (30, (30, 140, 50))]:
                draw.ellipse(
                    [bulb_cx - r, bulb_cy - r, bulb_cx + r, bulb_cy + r],
                    fill=alpha_color,
                )
            # Bright core
            draw.ellipse(
                [bulb_cx - radius, bulb_cy - radius, bulb_cx + radius, bulb_cy + radius],
                fill=COLOR_GREEN_GLOW,
                outline=(220, 255, 220),
                width=2,
            )
            # Inner specular highlight
            draw.ellipse(
                [bulb_cx - 8, bulb_cy - 12, bulb_cx - 2, bulb_cy - 6],
                fill=(255, 255, 255),
            )
        else:
            # Dark unpowered LED
            draw.ellipse(
                [bulb_cx - radius, bulb_cy - radius, bulb_cx + radius, bulb_cy + radius],
                fill=(25, 30, 35),
                outline=(60, 68, 75),
                width=2,
            )

    def render_waveform_chart(
        self,
        frames: List[SimulationFrame],
        pins: List[str],
        width: int = 900,
        height: int = 240,
    ) -> Image.Image:
        """Renders timing logic waveforms across all frames for the specified pins."""
        canvas = Image.new("RGB", (width, height), color=COLOR_BG)
        draw = ImageDraw.Draw(canvas)

        if not frames or not pins:
            draw.text((20, 20), "No simulation frames to plot.", fill=COLOR_TEXT_MUTED)
            return canvas

        draw.text((20, 12), "DIGITAL PIN LOGIC WAVEFORMS OVER TIME", fill=COLOR_CYAN)

        total_time = frames[-1].t_ms if frames[-1].t_ms > 0 else 1
        plot_x0 = 80
        plot_x1 = width - 30
        plot_w = plot_x1 - plot_x0

        # Draw time grid lines
        step_grid = 1000 if total_time >= 2000 else 500
        for grid_t in range(0, total_time + 1, step_grid):
            gx = plot_x0 + int((grid_t / total_time) * plot_w)
            draw.line([(gx, 40), (gx, height - 25)], fill=(30, 36, 44), width=1)
            draw.text((gx - 10, height - 20), f"{grid_t}ms", fill=COLOR_TEXT_MUTED)

        # Plot each pin waveform
        track_height = (height - 70) // max(1, len(pins[:4]))
        for idx, pin in enumerate(pins[:4]):
            y_base = 45 + idx * track_height
            y_high = y_base + 8
            y_low = y_base + track_height - 12

            # Pin label
            draw.text((15, y_base + (track_height // 3)), f"Pin {pin}", fill=COLOR_TEXT)
            # Baseline
            draw.line([(plot_x0, y_low), (plot_x1, y_low)], fill=(40, 48, 58), width=1)

            # Draw trace
            pts: List[Tuple[int, int]] = []
            prev_y = y_low
            for f in frames:
                fx = plot_x0 + int((f.t_ms / total_time) * plot_w)
                snap = f.pin_states.get(pin)
                val_y = y_high if (snap and snap.digital_state == "HIGH") else y_low

                # Step transition
                if pts and val_y != prev_y:
                    pts.append((fx, prev_y))
                pts.append((fx, val_y))
                prev_y = val_y

            if len(pts) >= 2:
                draw.line(pts, fill=COLOR_CYAN if idx % 2 == 0 else COLOR_GREEN_GLOW, width=2)

        return canvas


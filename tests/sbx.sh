#!/bin/bash
# Launch a browser briefly and report the GPU process sandbox state.
CH=$1; PORT=$2; N=sbx-$PORT
U=smartroomcontroller; UH=/home/$U; RUN=/run/user/$(id -u $U)
WL=$(ls $RUN | grep -m1 -E '^wayland-[0-9]+$'); SIG=$(ls -t $RUN/hypr | head -1)
D=$UH/.cache/sr-upstream/$N; rm -rf $D; runuser -u $U -- mkdir -p $D
runuser -u $U -- env XDG_RUNTIME_DIR=$RUN WAYLAND_DISPLAY=$WL HYPRLAND_INSTANCE_SIGNATURE=$SIG HOME=$UH "$CH" --enable-gpu --use-gl=angle --use-angle=gles-egl --render-node-override=/dev/dri/renderD128 --enable-features=AcceleratedVideoDecoder --ozone-platform=wayland --remote-debugging-port=$PORT --user-data-dir=$D --no-first-run --class=sr-upstream-sbx --window-size=320,200 about:blank >$D.err 2>&1 &
P=$!; sleep 8
for p in $(pgrep -u $U -f "user-data-dir=$D"); do
  c=$(tr '\0' ' ' </proc/$p/cmdline); t=$(echo "$c" | grep -o -- '--type=[a-z-]*'); 
  echo "${t:-browser} $(grep -E '^(Seccomp|NoNewPrivs):' /proc/$p/status | tr '\n' ' ') nodes: $(ls -l /proc/$p/fd 2>/dev/null | grep -o '/dev/\(video\|media\)[0-9a-z-]*' | sort -u | tr '\n' ' ')"
  echo "$c" | grep -o -- '--[a-z-]*sandbox[a-z-]*' | sort -u | tr '\n' ' '
done
kill $P; sleep 2; pkill -u $U -f "user-data-dir=$D"; grep -i -E 'sandbox|v4l2' $D.err | head -8

import bpy,math,json,shutil,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(r"C:\Users\DELL\Room")
OUT=ROOT/"work/scenes/attic-room-v05";OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/"work/scenes/attic-room-v04/Room-attic-v04.blend"))
scene=bpy.context.scene
def mat(name,c,rough=.65,metal=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*c,1)
 p=m.node_tree.nodes.get("Principled BSDF");p.inputs["Base Color"].default_value=(*c,1);p.inputs["Roughness"].default_value=rough;p.inputs["Metallic"].default_value=metal
 return m
ivory=mat("Heater ivory enamel",(.71,.69,.60),.4)
rear=mat("Heater grey steel",(.25,.26,.25),.52,.3)
dark=mat("Socket and vent dark interiors",(.013,.014,.012),.85)
socketmat=mat("Socket aged ivory plastic",(.57,.54,.42),.48)
socketinner=mat("Socket inner porcelain",(.66,.64,.53),.65)
metal=mat("Socket grounding metal",(.30,.28,.20),.25,.7)
def box(name,loc,size,m,b=.0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if m:o.data.materials.append(m)
 if b:
  mod=o.modifiers.new("Soft formed edges","BEVEL");mod.width=b;mod.segments=4
  o.modifiers.new("Weighted corner normals","WEIGHTED_NORMAL")
 return o
def cyl(name,loc,r,depth,m,axis="X"):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc)
 o=bpy.context.object;o.name=name
 if axis=="X":o.rotation_euler[1]=math.pi/2
 o.data.materials.append(m)
 bevel=o.modifiers.new("Edge bevel","BEVEL");bevel.width=min(.0015,depth/4);bevel.segments=3
 o.modifiers.new("Weighted normals","WEIGHTED_NORMAL");return o
def curve(name,pts,r,m):
 c=bpy.data.curves.new(name,"CURVE");c.dimensions="3D";c.bevel_depth=r;c.bevel_resolution=3
 sp=c.splines.new("BEZIER");sp.bezier_points.add(len(pts)-1)
 for p,co in zip(sp.bezier_points,pts):p.co=co;p.handle_left_type="AUTO";p.handle_right_type="AUTO"
 o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);c.materials.append(m);return o
def cut(o,cutter):
 bpy.context.view_layer.objects.active=o
 mod=o.modifiers.new("True opening","BOOLEAN");mod.operation="DIFFERENCE";mod.solver="EXACT";mod.object=cutter
 bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
# Keep refinements scoped to knee-wall heater and the four-gang outlet.
for o in list(bpy.data.objects):
 if o.name.startswith(("Electric wall heater","Heater grille","Heater vent","Knee outlet strip","Socket pin hole")):
  bpy.data.objects.remove(o,do_unlink=True)
yc=2.12
# New 60cm width and 17cm projection. Front stays 42cm; rear marked 33cm.
body=box("Heater rear chassis",(.084,yc,.54),(.132,.56,.33),rear,.006)
for yy in [yc-.18,yc+.18]:
 box("Heater wall bracket",(.012,yy,.54),(.024,.035,.27),rear,.003)
panel=box("Heater front panel",(.164,yc,.54),(.012,.60,.42),ivory)
# Cut three actual openings, then add spaced louvers.
for j in [-1,0,1]:
 gy=yc+j*.187
 hole=box("temporary vent cutter",(.164,gy,.666),(.060,.167,.142),None)
 cut(panel,hole)
 box("Heater grille dark backing",(.153,gy,.666),(.003,.169,.144),dark)
 for i in range(12):
  z=.6015+i*.0117
  l=box("Heater angled louver",(.164,gy,z),(.010,.164,.0065),ivory,.0012)
  l.rotation_euler[1]=math.radians(-12)
be=panel.modifiers.new("Rolled panel edges","BEVEL");be.width=.002;be.segments=3
panel.modifiers.new("Panel corner normals","WEIGHTED_NORMAL")
# Thin horizontal fold separates grille from the blank lower panel.
box("Heater lower horizontal crease",(.1704,yc,.580),(.0008,.565,.002),rear)
# Rear top controller and round adjustment knob, visible from above.
box("Heater control housing",(.080,yc+.218,.717),(.105,.090,.042),rear,.004)
cyl("Heater thermostat knob",(.080,yc+.218,.746),.021,.016,ivory,"Z")
box("Heater knob indicator",(.080,yc+.206,.7545),(.003,.010,.001),rear,.0004)
for i in range(7):
 ang=math.radians(-140+i*35)
 cyl("Heater dial tick",(.080+.029*math.cos(ang),yc+.218+.029*math.sin(ang),.739),.0012,.001,ivory,"Z")
# Rear side fasteners and side vent slits.
for z in [.408,.672]:
 cyl("Heater side screw",(.085,yc-.281,z),.003,.003,dark,"Z").rotation_euler[0]=math.pi/2
for z in [.428,.440,.452]:
 box("Heater rear side slot",(.08,yc-.281,z),(.033,.002,.004),dark,.0005)
curve("Heater lower cable",[(.045,yc+.10,.376),(.055,yc+.12,.348),(.035,yc+.17,.340),(.007,yc+.19,.367)],.0035,dark)
# Four sockets: 29cm frame, 24cm above floor, nearest edge 27cm from gable corner.
frame_w,frame_h=.29,.09
frame_y=4.12-.27-frame_w/2
frame_z=.24+frame_h/2
frame=box("Four gang socket outer frame",(.016,frame_y,frame_z),(.024,frame_w,frame_h),socketmat,.005)
for j in range(4):
 sy=frame_y+(j-1.5)*.069
 surround=box("Socket individual face %d"%(j+1),(.032,sy,frame_z),(.011,.065,.068),socketinner,.003)
 # Hollow the face around the circular cup.
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=.0225,depth=.05,location=(.032,sy,frame_z),rotation=(0,math.pi/2,0))
 cut(surround,bpy.context.object)
 # Actual recessed cup: dished surface, with bevelled ring.
 bpy.ops.mesh.primitive_torus_add(major_radius=.0205,minor_radius=.002,major_segments=48,minor_segments=12,location=(.036,sy,frame_z),rotation=(0,math.pi/2,0))
 tor=bpy.context.object;tor.name="Socket recessed rim %d"%(j+1);tor.data.materials.append(socketinner)
 if j<2:
  cyl("Socket recessed cup %d"%(j+1),(.029,sy,frame_z),.0208,.004,socketinner)
  for dy in [-.009,.009]:
   cyl("Socket pin aperture %d"%(j+1),(.0315,sy+dy,frame_z+.001),.0032,.002,dark)
  cyl("Socket grounding pin %d"%(j+1),(.036,sy,frame_z+.0125),.0022,.010,metal)
 else:
  cyl("Socket dark insert %d"%(j+1),(.032,sy,frame_z),.0214,.008,dark)
  # Shape detail only: photo does not establish whether these are plugs or covers.
  box("Socket dark insert highlight %d"%(j+1),(.0365,sy,frame_z+.010),(.001,.010,.003),rear,.0005)
# Detail camera stays below slope and looks at the heater and sockets together.
def camera(name,loc,target,lens):
 bpy.ops.object.camera_add(location=loc);o=bpy.context.object;o.name=name;o.data.lens=lens;o.data.clip_start=.02;o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler();return o
camdetail=camera("06 Heater and sockets",(1.55,2.90,1.40),(.08,2.91,.50),26)
camheat=camera("07 Heater closeup",(.88,1.24,1.04),(.08,2.12,.54),35)
camsocket=camera("08 Socket closeup",(.63,3.25,.60),(.035,frame_y,frame_z),58)
scene.camera=bpy.data.objects["01 View from entrance"]
scene["heater_dimensions_note"]="New 60cm width, 17cm projection, 33cm rear. Front 42cm / rear 33cm confirmed by user; 33cm floor gap retained."
scene["socket_dimensions_note"]="29x9cm chosen from 8/9cm labels. Bottom 24cm, nearest edge 27cm from gable corner. Dark insert types uncertain."
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"Room-attic-v05.blend"))
for o in bpy.context.selected_objects:o.select_set(False)
for o in scene.objects:
 if o.type in {"MESH","CURVE"} and not o.name.startswith("Exterior"):o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/"Room-attic-v05.glb"),export_format="GLB",use_selection=True,export_cameras=False,export_lights=False)
# GPU rendering, then inspect all changed components close-up.
prefs=bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type="OPTIX";prefs.get_devices()
for d in prefs.devices:d.use=d.type!="CPU"
scene.cycles.device="GPU" if any(d.type!="CPU" for d in prefs.devices) else "CPU"
scene.cycles.samples=64;scene.render.resolution_x=1400;scene.render.resolution_y=1050
for cam,n in [(scene.camera,"01-interior.png"),(camdetail,"06-heater-and-sockets.png"),(camheat,"07-heater-closeup.png"),(camsocket,"08-socket-closeup.png")]:
 scene.camera=cam;scene.render.filepath=str(OUT/n);bpy.ops.render.render(write_still=True)
refs=ROOT/"work/inspection/measurements-v05";refs.mkdir(exist_ok=True)
files=["c9cc2cff-a182-4075-9479-b1c1a4b44018","fbc07a4a-3566-4723-bc31-47dc3cf390d0","7fe27ba4-5fc2-4fa2-b62d-d345b352b5c1"]
hashes=[]
for i,n in enumerate(files,1):
 p=Path(r"C:\Users\DELL\AppData\Local\Temp")/("codex-clipboard-"+n+".jpg")
 shutil.copy2(p,refs/("reference-%d.jpg"%i));hashes.append(hashlib.sha256(p.read_bytes()).hexdigest())
review={"heater":{"front_width_m":.60,"front_height_m":.42,"rear_height_m":.33,"projection_from_wall_m":.17,"front_bottom_m":.33,"body_height_interpretation":"User confirmed 33cm grey rear chassis and 42cm white front","lengthwise_position":"estimated, unchanged","controls":"knob and slots visually approximated; no manufacturer identity asserted"},"sockets":{"outer_width_m":.29,"outer_height_m":.09,"alternative_height_label_m":.08,"bottom_from_floor_m":.24,"nearest_edge_to_gable_wall_m":.27,"count":4,"appearance":"two light socket cups and two dark inserts; dark insert function not established","depth_and_internal_details":"estimated"},"reference_sha256":hashes,"scope":"heater and knee-wall socket strip only"}
(OUT/"measurement-review-v05.json").write_text(json.dumps(review,indent=2),encoding="utf-8")
print("V05_DONE")


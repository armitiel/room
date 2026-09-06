import bpy, math, json, random
from mathutils import Vector
from pathlib import Path
random.seed(12)
OUT=Path(r"C:\Users\DELL\Room\work\scenes\attic-room-v03")
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
for block in bpy.data.materials: bpy.data.materials.remove(block)
W,L,H,K,R=2.90,4.12,2.32,1.07,1.20
def mat(name,color,rough=.7,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=m.node_tree.nodes.get("Principled BSDF");bs.inputs["Base Color"].default_value=(*color,1);bs.inputs["Roughness"].default_value=rough;bs.inputs["Metallic"].default_value=metal
 return m
wall=mat("Pale cool grey walls",(.61,.65,.68)); ceiling=mat("White ceiling",(.82,.83,.83))
wood=mat("Dark walnut joinery",(.17,.058,.025)); floor=mat("Warm brown wood flooring",(.26,.105,.052))
trim=mat("White trim",(.88,.87,.83)); linen=mat("Muted lilac bedding",(.42,.32,.41)); fabric=mat("Grey upholstered bed",(.30,.34,.35))
glass=mat("Window glass - simplified",(.58,.75,.79),.18);black=mat("Dark metal",(.055,.05,.045),.28,.7)
mint=mat("Mint bedside stand",(.12,.37,.30)); cream=mat("Cream cushion",(.63,.57,.45)); doorGlass=mat("Frosted dark door glass",(.10,.115,.11),.32)
def box(name,loc,scale,material,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=scale
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if material:o.data.materials.append(material)
 if bevel:
  mod=o.modifiers.new("Soft edges","BEVEL");mod.width=bevel;mod.segments=3
  o.modifiers.new("Weighted normals","WEIGHTED_NORMAL")
 return o
def mesh(name,verts,faces,material):
 me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
 o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);o.data.materials.append(material)
 return o
def beam(name,a,b,r,material):
 mid=(Vector(a)+Vector(b))/2; d=Vector(b)-Vector(a)
 bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=r,depth=d.length,location=mid)
 o=bpy.context.object;o.name=name;o.rotation_euler=d.to_track_quat("Z","Y").to_euler();o.data.materials.append(material);return o
def area(name,loc,target,power,size,color=(1,1,1)):
 bpy.ops.object.light_add(type="AREA",location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape="DISK";o.data.size=size;o.data.color=color;o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler()
def camera(name,loc,target,lens=23):
 bpy.ops.object.camera_add(location=loc);o=bpy.context.object;o.name=name;o.data.lens=lens;o.data.clip_start=.03;o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler();return o
# Room topology from photos, all dimensions provisional.
box("Floor slab",(W/2,L/2,-.075),(W,L,.15),floor)
for i in range(16):
 x=(i+.5)*W/16
 for j in range(5):
  y=(j+.5)*L/5
  c=mat("Plank_%02d_%02d"%(i,j),(.23+random.random()*.09,.085+random.random()*.035,.035+random.random()*.025))
  box("Floorboard",(x,y,.005),(W/16-.003,L/5-.004,.012),c,.002)
knee=box("Knee wall",( -.06,L/2,K/2),(.12,L,K),wall)
# Rear gable wall with true rectangular window opening.
ox1=W-.56
ox0=ox1-1.13
oz1=H-.20
oz0=oz1-1.40 # opening height inferred from confirmed frame + 35mm border
wx0,wx1,wz0,wz1=ox0+.035,ox1-.035,oz0+.035,oz1-.035
profile=[(0,0),(W,0),(W,H),(R,H),(0,K)]
front=mesh("Entrance end wall",[(x,0,z) for x,z in profile],[(0,1,2,3,4)],wall)
mesh("Window end left",[(0,L,0),(ox0,L,0),(ox0,L,H),(R,L,H),(0,L,K)],[(0,1,2,3,4)],wall)
box("Window end right",((ox1+W)/2,L,H/2),(W-ox1,.12,H),wall)
box("Under gable window",((ox0+ox1)/2,L,oz0/2),(ox1-ox0,.12,oz0),wall)
box("Above gable window",((ox0+ox1)/2,L,(oz1+H)/2),(ox1-ox0,.12,H-oz1),wall)
# High wall and door opening close to entrance end.
d0,d1,dh=.12,1.04,2.04 # 12cm corner offset is provisional (partly cropped label)
box("High wall before door",(W+.06,d0/2,H/2),(.12,d0,H),wall)
box("High wall after door",(W+.06,(d1+L)/2,H/2),(.12,L-d1,H),wall)
box("High wall above door",(W+.06,(d0+d1)/2,(dh+H)/2),(.12,d1-d0,H-dh),wall)
box("Door leaf",(W+.005,(d0+d1)/2,(dh-.035)/2),(.055,d1-d0-.07,dh-.035),wood,.008)
for y in [d0+.0175,d1-.0175]:box("Door frame",(W-.025,y,dh/2),(.08,.035,dh),wood,.005)
box("Door lintel",(W-.025,(d0+d1)/2,dh-.0175),(.08,d1-d0,.035),wood,.004)
box("Door glass",(W-.033,(d0+d1)/2,1.34),(.008,.64,1.02),doorGlass,.05)
for z in [.90,1.18,1.46,1.74]:box("Door glass muntin",(W-.045,(d0+d1)/2,z),(.018,.65,.018),wood,.004)
box("Door vertical muntin",(W-.047,(d0+d1)/2,1.35),(.02,.018,.99),wood,.004)
beam("Door handle",(W-.08,d0+.14,.99),(W-.08,d0+.30,.99),.014,black)
# Skew roof with opening. x-z slope, y runs length of room.
def roofz(x): return K+(H-K)*x/R
# Opening measured along slope 1.65m; outer width .75m, inner width .72m.
u=Vector((R,0,H-K)).normalized()
n=Vector((-u.z,0,u.x))
sx0=.025
sx1=sx0+1.65*u.x
sy0,sy1=1.09,1.84 # offset from entrance end inferred from photo
roofs=[]
for x0,x1,y0,y1 in [(0,sx0,0,L),(sx1,R,0,L),(sx0,sx1,0,sy0),(sx0,sx1,sy1,L)]:
 roofs.append(mesh("Sloping ceiling",[(x0,y0,roofz(x0)),(x1,y0,roofz(x1)),(x1,y1,roofz(x1)),(x0,y1,roofz(x0))],[(0,1,2,3)],ceiling))
flat=box("Flat ceiling",((W+R)/2,L/2,H+.025),(W-R,L,.05),ceiling);roofs.append(flat)
# Solve a consistent tapered recess: .38m lower and .42m upper side edges.
# Geometry is one plausible interpretation, not a measured roof thickness.
lo,hi=0,.379
for _ in range(70):
 depth=(lo+hi)/2
 total=math.sqrt(.38**2-depth**2-.015**2)+math.sqrt(.42**2-depth**2-.015**2)
 if total>.67:lo=depth
 else:hi=depth
depth=(lo+hi)/2
lower_run=math.sqrt(.38**2-depth**2-.015**2)
outer0=Vector((sx0,sy0,roofz(sx0)))
ib=outer0+u*lower_run+n*depth+Vector((0,.015,0))
inner=[ib,ib+u*.98,ib+u*.98+Vector((0,.72,0)),ib+Vector((0,.72,0))]
outer=[outer0,outer0+u*1.65,outer0+u*1.65+Vector((0,.75,0)),outer0+Vector((0,.75,0))]
for i in range(4):
 mesh("Skylight reveal %d"%i,[outer[i],outer[(i+1)%4],inner[(i+1)%4],inner[i]],[(0,1,2,3)],ceiling)
def sp(t,y):return ib+u*t+Vector((0,y,0))
for a,b,c,d in [(0,.045,0,.72),(.935,.98,0,.72),(.045,.935,0,.045),(.045,.935,.675,.72)]:
 mesh("Skylight timber frame",[sp(a,c),sp(b,c),sp(b,d),sp(a,d)],[(0,1,2,3)],wood)
mesh("Skylight glass",[sp(.045,.045),sp(.935,.045),sp(.935,.675),sp(.045,.675)],[(0,1,2,3)],glass)
# Gable window frame and pane.
for x in [wx0+.0325,wx1-.0325]:box("Gable window jamb",(x,L+.08,(wz0+wz1)/2),(.065,.12,wz1-wz0),wood,.006)
for z in [wz0+.0325,wz1-.0325]:box("Gable window rail",((wx0+wx1)/2,L+.08,z),(wx1-wx0,.12,.065),wood,.006)
box("Gable glass",((wx0+wx1)/2,L+.085,(wz0+wz1)/2),(wx1-wx0-.06,.018,wz1-wz0-.07),glass)
hole=[(ox0,L-.06,oz0),(ox1,L-.06,oz0),(ox1,L-.06,oz1),(ox0,L-.06,oz1)]
inside=[(wx0,L+.02,wz0),(wx1,L+.02,wz0),(wx1,L+.02,wz1),(wx0,L+.02,wz1)]
for i in range(4):mesh("Gable window reveal %d"%i,[hole[i],hole[(i+1)%4],inside[(i+1)%4],inside[i]],[(0,1,2,3)],wall)
box("Window sill",((wx0+wx1)/2,L-.13,wz0-.035),(wx1-wx0+.16,.32,.045),trim,.008)
beam("Curtain rod",(wx0-.17,L-.20,H-.10),(wx1+.14,L-.20,H-.10),.012,black)
# Skirting around perimeter.
box("Knee skirting",(.025,L/2,.045),(.035,L,.09),wood)
box("Window skirting",(W/2,L-.015,.045),(W,.035,.09),wood)
box("Entrance skirting",(W/2,.015,.045),(W,.035,.09),wood)
box("High wall skirting",(W-.015,(d1+L)/2,.045),(.035,L-d1,.09),wood)
# Bed: headboard along high wall, bed length across room.
bx,by=2.09,3.30
box("Bed upholstered base",(bx,by,.22),(2.05,1.66,.32),fabric,.065)
box("Mattress",(bx-.025,by,.44),(2.02,1.61,.23),linen,.085)
box("Headboard",(3.10,by,.62),(.14,1.72,1.05),fabric,.065)
# Slightly undulating duvet surface.
verts=[];faces=[]
nx,ny=40,32
for i in range(nx+1):
 for j in range(ny+1):
  x=1.10+i/nx*1.52;y=2.51+j/ny*1.58
  z=.578+.012*math.sin(i*.8+j*.36)+.008*math.sin(j*.9-i*.32)
  verts.append((x,y,z))
for i in range(nx):
 for j in range(ny):
  a=i*(ny+1)+j;faces.append((a,a+1,a+ny+2,a+ny+1))
duvet=mesh("Duvet simplified folds",verts,faces,linen)
for poly in duvet.data.polygons:poly.use_smooth=True
for y in [2.89,3.66]:
 o=box("Pillow",(2.77,y,.63),(.47,.65,.15),cream,.07);o.rotation_euler[1]=-.10
# Small bedside green stand seen under window.
box("Bedside top",(2.96,4.27,.42),(.40,.36,.055),mint,.008)
for x in [2.80,3.12]:
 for y in [4.14,4.40]:box("Bedside leg",(x,y,.21),(.035,.035,.42),mint)
box("Bedside shelf",(2.96,4.27,.11),(.37,.33,.04),mint)
# Wall heater on knee wall, shelf on gable left.
box("Electric wall heater",(.085,2.12,.54),(.14,.56,.42),trim,.012)
for z in [.62,.65,.68,.71]:box("Heater vent",(.163,2.12,z),(.006,.49,.009),black)
box("Floating shelf",(.71,L-.13,1.10),(1.08,.28,.045),wood,.01)
for i in range(4):box("Shelf item",(.32+i*.18,L-.10,1.18),(.13,.13,.12),cream,.005)
# Simplified ceiling fixture.
beam("Ceiling fixture stem",(2.35,2.30,H),(2.35,2.30,H-.10),.02,black)
beam("Ceiling fixture rail",(1.95,1.60,H-.12),(2.65,3.0,H-.12),.012,black)
for i in range(5):
 t=i/4;x=1.95+.70*t;y=1.6+1.4*t
 beam("Spotlight",(x,y,H-.12),(x,y,H-.25),.045,trim)

# Reposition furnishing group to measured high wall / end wall.
prefixes=("Bed upholstered","Mattress","Headboard","Duvet","Pillow","Bedside")
for obj in list(bpy.data.objects):
 if obj.name.startswith(prefixes):
  obj.location.x -= .30
  obj.location.y -= .38
# Lighting and cameras.
area("Soft window daylight",(2.10,3.86,1.9),(1.2,1.2,.6),180,1.1,(.84,.91,1))
area("Skylight daylight",(.40,1.46,1.70),(2.6,2,.3),140,.8,(.90,.94,1))
area("Interior fill",(2.1,1.0,2.15),(1.8,3,.5),95,2.2,(1,.90,.81))
scene=bpy.context.scene
scene.unit_settings.system="METRIC"
scene.render.engine="CYCLES";scene.cycles.samples=16
scene.cycles.use_denoising=True
scene.world.color=(.27,.27,.27)
scene.render.resolution_x=1400;scene.render.resolution_y=1050;scene.render.resolution_percentage=100
scene.view_settings.view_transform="AgX"
cam1=camera("01 View from entrance",(2.55,.36,1.60),(1.44,2.90,1.12),20)
cam2=camera("02 View towards door",(1.45,3.82,1.58),(1.94,.53,1.20),20)
cam3=camera("03 Cutaway",(7.5,-7.5,7.6),(1.6,2.25,.85),48)
cam4=camera("04 Skylight detail",(2.05,2.24,1.20),(.57,1.46,1.80),27)
scene.camera=cam1
# Default viewport opens at useful interior angle.
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=="VIEW_3D":
   a.spaces.active.region_3d.view_perspective="CAMERA"
scene["reconstruction_status"]="Photo-guided approximation; not a photogrammetric scan."
scene["dimensions_status"]="Original heights retained by user. Door/heater/reveals updated from AR measurements; several placements inferred."
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"Room-attic-v03.blend"))
bpy.ops.export_scene.gltf(filepath=str(OUT/"Room-attic-v03.glb"),export_format="GLB",export_cameras=False,export_lights=False)
for cam,filename in [(cam1,"01-interior.png"),(cam2,"02-door.png"),(cam4,"04-skylight.png")]:
 scene.camera=cam;scene.render.filepath=str(OUT/filename);bpy.ops.render.render(write_still=True)
# Cutaway preview only: original blend keeps full shell.
for o in roofs+[front]:o.hide_render=True
area("Cutaway softbox",(2,-1,7),(1.6,2,0),650,5)
scene.camera=cam3;scene.render.filepath=str(OUT/"03-cutaway.png");bpy.ops.render.render(write_still=True)
(OUT/"dimensions.json").write_text(json.dumps({"status":"user_ar_measurements_with_conflict","width_m":W,"length_m":L,"max_height_m":H,"knee_wall_height_m":K,"slope_run_m":R,"bed_m":[2.05,1.66],"source":"18 photos, 22 video frames, 11 user AR measurement screenshots","note":"Manual visual reconstruction, no photogrammetry. Slope measured 1.97m conflicts with envelope-derived 1.733m; gable window frame 1.06 x 1.33 m confirmed by user."},indent=2))
print("ROOM_DONE",len(bpy.data.objects))


import bpy, math, json, random, numpy as np
from pathlib import Path
from mathutils import Vector
random.seed(42)
ROOT=Path(r"C:\Users\DELL\Room")
OUT=ROOT/"work/scenes/attic-room-v04";OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/"work/scenes/attic-room-v03/Room-attic-v03.blend"))
scene=bpy.context.scene
def remove_prefix(prefixes):
 for o in list(bpy.data.objects):
  if o.name.startswith(prefixes):bpy.data.objects.remove(o,do_unlink=True)
def mat(name,color,rough=.6,metal=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
 bs=m.node_tree.nodes.get("Principled BSDF");bs.inputs["Base Color"].default_value=(*color,1);bs.inputs["Roughness"].default_value=rough;bs.inputs["Metallic"].default_value=metal
 return m
def setcol(name,c,r=None):
 m=bpy.data.materials.get(name)
 if m:
  m.diffuse_color=(*c,1);bs=m.node_tree.nodes.get("Principled BSDF");bs.inputs["Base Color"].default_value=(*c,1)
  if r is not None:bs.inputs["Roughness"].default_value=r
 return m
def box(name,loc,size,m,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 o.data.materials.append(m)
 if bevel:
  mod=o.modifiers.new("Rounded edges","BEVEL");mod.width=bevel;mod.segments=3
  o.modifiers.new("Weighted normals","WEIGHTED_NORMAL")
 return o
def mesh(name,verts,faces,m,uvs=None):
 me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
 o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);me.materials.append(m)
 if uvs:
  uv=me.uv_layers.new(name="UVMap")
  for poly in me.polygons:
   for li in poly.loop_indices:uv.data[li].uv=uvs[me.loops[li].vertex_index]
 return o
def beam(name,a,b,r,m):
 v=Vector(b)-Vector(a)
 bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=r,depth=v.length,location=(Vector(a)+Vector(b))/2)
 o=bpy.context.object;o.name=name;o.rotation_euler=v.to_track_quat("Z","Y").to_euler();o.data.materials.append(m);return o
def curve(name,pts,r,m):
 c=bpy.data.curves.new(name,"CURVE");c.dimensions="3D";c.bevel_depth=r;c.bevel_resolution=3
 sp=c.splines.new("POLY");sp.points.add(len(pts)-1)
 for p,co in zip(sp.points,pts):p.co=(*co,1)
 o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);c.materials.append(m);return o
def teximg(name,array):
 h,w=array.shape[:2];im=bpy.data.images.new(name,width=w,height=h)
 rgba=np.ones((h,w,4),dtype=np.float32);rgba[:,:,:3]=np.clip(array,0,1)
 im.pixels.foreach_set(rgba.ravel());im.filepath_raw=str(OUT/(name+".png"));im.file_format="PNG";im.save();im.pack();return im
def textured(name,im,rough=.55,bump=.002):
 m=mat(name,(.3,.3,.3),rough);n=m.node_tree.nodes;l=m.node_tree.links;bs=n.get("Principled BSDF")
 t=n.new("ShaderNodeTexImage");t.image=im;l.new(t.outputs["Color"],bs.inputs["Base Color"])
 if bump:
  b=n.new("ShaderNodeBump");b.inputs["Distance"].default_value=bump;b.inputs["Strength"].default_value=.2;l.new(t.outputs["Color"],b.inputs["Height"]);l.new(b.outputs["Normal"],bs.inputs["Normal"])
 return m
# Packed procedural image textures: portable in .blend and GLB.
N=1024
yy,xx=np.mgrid[0:N,0:N].astype(float)/N
rng=np.random.default_rng(6)
warp=xx+.014*np.sin(yy*19)+.004*np.sin(yy*57+xx*9)
grain=np.sin(warp*480+np.sin(yy*13)*2)*.022+np.sin(warp*1500+yy*8)*.009
broad=.030*np.sin(warp*31)+.014*np.sin(warp*83+yy*3)
woodarr=np.stack([.30+broad+grain,.17+broad*.70+grain*.7,.09+broad*.48+grain*.5],axis=-1)
woodarr+=rng.normal(0,.003,(N,N,1))
woodim=teximg("walnut-grain",woodarr)
wood=textured("Walnut with grain",woodim,.35,.001)
floor=textured("Floorboard grain",woodim,.42,.0015)
# Fabric stripe runs along bed length.
stripe=(np.sin(xx*math.tau*100)>0).astype(float)
weave=.006*np.sin(xx*math.tau*500)*np.sin(yy*math.tau*480)
cloth=np.stack([.45+stripe*.085+weave,.395+stripe*.080+weave,.43+stripe*.082+weave],axis=-1)
clothim=teximg("lilac-pinstripe",cloth)
linen=textured("Lilac fine striped cotton",clothim,.83,.001)
# Fine upholstery texture.
noise=rng.random((512,512,1))*.09
up=teximg("grey-upholstery",np.repeat(noise,3,axis=2)+np.array([.34,.35,.355])[None,None,:])
upholstery=textured("Grey woven upholstery",up,.9,.001)
setcol("Pale cool grey walls",(.37,.40,.43),.88)
setcol("White ceiling",(.64,.65,.66),.9)
trim=setcol("White trim",(.76,.74,.68),.65)
bronze=setcol("Dark metal",(.09,.075,.055),.28)
gold=mat("Muted golden cushion",(.18,.095,.03),.42)
purple=mat("Deep mauve cushion",(.10,.073,.11),.82)
for o in list(bpy.data.objects):
 if o.type=="MESH":
  for slot in o.material_slots:
   if slot.material and slot.material.name=="Dark walnut joinery":slot.material=wood
   if slot.material and slot.material.name=="Grey upholstered bed":slot.material=upholstery
# Replace floor with staggered boards and stable planar UVs.
remove_prefix(("Floorboard",))
W,L=2.9,4.12
for i in range(16):
 x0=i*W/16;x1=(i+1)*W/16
 y=-1.12+random.uniform(0,1.12)
 while y<L:
  y0=max(0,y);y1=min(L,y+1.12)
  if y1>y0:
   o=box("Staggered wood board",((x0+x1)/2,(y0+y1)/2,.006),(x1-x0-.0015,y1-y0-.002,.012),floor,.0008)
   uv=o.data.uv_layers.active; offset=random.random()*6
   for poly in o.data.polygons:
    for li in poly.loop_indices:
     v=o.data.vertices[o.data.loops[li].vertex_index].co
     uv.data[li].uv=(v.x*.8+offset,v.y*.60+random.random()*.00001)
  y+=1.12
bpy.data.objects["Floating shelf"].dimensions.x=.98
bpy.data.objects["Floating shelf"].location.x=.65
# Headboard has a visible centre joint, as in source photos.
remove_prefix(("Headboard",))
for y in [2.49,3.35]:box("Headboard padded panel",(2.80,y,.62),(.14,.848,1.05),upholstery,.022)
# More natural fitted, draped cover.
remove_prefix(("Duvet","Pillow"))
bpy.data.objects["Mattress"].data.materials.clear();bpy.data.objects["Mattress"].data.materials.append(linen)
verts=[];faces=[];uvs=[];nx,ny=144,112
for i in range(nx+1):
 for j in range(ny+1):
  u=i/nx;v=j/ny;x=.70+2.08*u;y=2.035+1.77*v
  edge=max(0,(.79-x)/.09,(2.115-y)/.08,(y-3.725)/.08)
  z=.574-.17*min(edge,1)**1.7
  envelope=math.exp(-((x-1.78)/.58)**2-((y-2.94)/.60)**2)
  z+=envelope*(.017*math.sin(41*x+18*y+1.8*math.sin(13*y))+.011*math.sin(69*x-23*y+2*math.sin(11*x))+.005*math.sin(112*x+53*y))
  z+=.012*math.sin(y*28+x*6)*math.exp(-((x-.9)/.26)**2)
  verts.append((x,y,z));uvs.append((v,u))
for i in range(nx):
 for j in range(ny):
  a=i*(ny+1)+j;faces.append((a,a+ny+1,a+ny+2,a+1))
duvet=mesh("Draped striped duvet",verts,faces,linen,uvs)
for p in duvet.data.polygons:p.use_smooth=True
sol=duvet.modifiers.new("Fabric thickness","SOLIDIFY");sol.thickness=.002
# Puff cushions with irregular silhouette and a sewn edge.
def pillow(name,loc,size,material,rot):
 n=36;vs=[];fs=[];uv=[];a,b=size
 for side in [1,-1]:
  for i in range(n+1):
   for j in range(n+1):
    u=-1+2*i/n;v=-1+2*j/n
    z=side*(.015+.075*max(0,(1-u**4)*(1-v**4))**.55)
    z+=.007*math.sin(17*u+9*v)*(1-abs(u))*(1-abs(v))
    vs.append((u*a/2,v*b/2,z));uv.append(((u+1)/2,(v+1)/2))
 for s in [0,1]:
  for i in range(n):
   for j in range(n):
    k=s*(n+1)**2+i*(n+1)+j;f=(k,k+n+1,k+n+2,k+1);fs.append(f if s==0 else f[::-1])
 count=(n+1)**2
 boundary=list(range(n+1))+[i*(n+1)+n for i in range(1,n+1)]+[n*(n+1)+j for j in range(n-1,-1,-1)]+[i*(n+1) for i in range(n-1,0,-1)]
 for i,k in enumerate(boundary):
  q=boundary[(i+1)%len(boundary)];fs.append((k,q,q+count,k+count))
 ob=mesh(name,vs,fs,material,uv);ob.location=loc;ob.rotation_euler=rot
 for p in ob.data.polygons:p.use_smooth=True
 return ob
pillow("Mauve cushion",(2.61,3.30,.75),(.54,.63),purple,(.1,1.0,-.08))
pillow("Gold cushion",(2.57,2.83,.73),(.51,.61),gold,(-.18,.78,.12))
pillow("Small cream cushion",(2.45,2.56,.67),(.40,.47),bpy.data.materials["Cream cushion"],(.05,.4,-.2))
# Arch-top glazed door and curved muntins.
remove_prefix(("Door glass","Door vertical muntin"))
yc=.58;half=.30
outline=[(yc-half,.88)]
for i in range(25):
 t=-1+2*i/24;outline.append((yc+t*half,1.74+.10*(1-t*t)))
outline.append((yc+half,.88))
mesh("Door arched frosted glass",[(2.856,y,z) for y,z in outline],[tuple(range(len(outline)))],bpy.data.materials["Frosted dark door glass"])
for z in [.88,1.18,1.48,1.74]:
 pts=[(2.849,yc+half*t,z+.08*(1-t*t)) for t in [-1+i/15 for i in range(31)]]
 curve("Door curved wood muntin",pts,.009,wood)
curve("Door central muntin",[(2.849,yc,.88),(2.849,yc,1.84)],.009,wood)
for y in [yc-half,yc+half]:curve("Door glazed border",[(2.849,y,.88),(2.849,y,1.74)],.012,wood)
# Lower raised panel.
box("Door lower raised panel",(2.852,yc,.43),(.018,.59,.62),wood,.026)
# Heater grille with vertical dividers; preserve measured outer box.
remove_prefix(("Heater vent",))
for k in range(10):
 z=.618+k*.0107
 for y in [1.948,2.12,2.292]:box("Heater grille slot",(.157,y,z),(.003,.147,.0045),bronze)
# Ceiling moulding on observed boundaries.
curve("High wall ceiling moulding",[(2.88,0,2.305),(2.88,4.12,2.305)],.013,trim)
curve("Entrance ceiling moulding",[(0,.015,1.07),(1.2,.015,2.305),(2.88,.015,2.305)],.012,trim)
curve("Gable ceiling moulding",[(0,4.1,1.07),(1.2,4.1,2.305),(2.88,4.1,2.305)],.012,trim)
curve("Knee slope seam",[(.009,0,1.07),(.009,4.12,1.07)],.009,trim)
# Replace straight fixture by articulated five-spot fixture.
remove_prefix(("Ceiling fixture","Spotlight"))
beam("Lamp canopy",(2.13,2.29,2.29),(2.13,2.29,2.32),.09,bronze)
beam("Lamp canopy connector",(2.13,2.29,2.29),(2.13,2.29,2.20),.012,bronze)
points=[(1.74,1.62,2.20),(2.22,1.89,2.20),(2.04,2.71,2.20),(2.50,2.98,2.20)]
for a,b in zip(points,points[1:]):beam("Lamp articulated rail",a,b,.011,bronze)
for p in points[1:3]:beam("Lamp hinge",(p[0],p[1],2.17),(p[0],p[1],2.24),.019,bronze)
for x,y in [(1.80,1.65),(2.17,1.97),(2.12,2.31),(2.06,2.64),(2.43,2.94)]:
 beam("Lamp short neck",(x,y,2.20),(x,y,2.12),.012,bronze)
 bpy.ops.mesh.primitive_cone_add(vertices=40,radius1=.054,radius2=.033,depth=.10,location=(x,y,2.07))
 o=bpy.context.object;o.name="Frosted spotlight shade";o.data.materials.append(trim)
# Sockets and switch shapes observed in photos, placement approximate.
socket=mat("Ivory switch plates",(.69,.68,.60),.5)
for yy,zz in [(1.20,1.12),(1.31,1.12),(1.38,.22)]:
 box("Wall socket plate",(2.892,yy,zz),(.018,.07,.075),socket,.008)
box("Knee outlet strip",(.011,3.19,.25),(.018,.30,.067),socket,.008)
for y in [3.10,3.18,3.26]:
 for z in [.242,.258]:beam("Socket pin hole",(.022,y,z),(.024,y,z),.004,bronze)
# More realistic glass: retain glazing plane, expose a simple 3D garden backdrop.
gm=mat("Clear window glazing",(.92,.96,.99),.08)
bs=gm.node_tree.nodes.get("Principled BSDF");bs.inputs["Transmission Weight"].default_value=1;bs.inputs["IOR"].default_value=1.45;bs.inputs["Alpha"].default_value=.20
gm.surface_render_method="DITHERED"
for name in ["Gable glass","Skylight glass"]:
 bpy.data.objects[name].data.materials.clear();bpy.data.objects[name].data.materials.append(gm)
# Exterior appearance uses a UV-mapped fragment of the supplied photograph.
# It is a flat reference backdrop, not a reconstructed garden.
photo=bpy.data.images.load(str(ROOT/"work/inspection/IMG_0416(1).jpg"),check_existing=True);photo.pack()
pm=bpy.data.materials.new("Exterior photo reference");pm.use_nodes=True
nodes=pm.node_tree.nodes;links=pm.node_tree.links;nodes.clear()
po=nodes.new("ShaderNodeOutputMaterial");em=nodes.new("ShaderNodeEmission");em.inputs["Strength"].default_value=1.4
it=nodes.new("ShaderNodeTexImage");it.image=photo
links.new(it.outputs["Color"],em.inputs["Color"]);links.new(em.outputs[0],po.inputs[0])
mesh("Exterior photo backdrop",[(.35,5.0,.15),(3.20,5.0,.15),(3.20,5.0,3.25),(.35,5.0,3.25)],[(0,1,2,3)],pm,
 [(280/1050,1-650/1400),(500/1050,1-650/1400),(500/1050,1-365/1400),(260/1050,1-358/1400)])
# Photo plane only for camera rays, not an emissive light source.
plate=bpy.data.objects["Exterior photo backdrop"]
plate.visible_diffuse=False;plate.visible_glossy=False;plate.visible_transmission=True;plate.visible_shadow=False
# Daylight anchored at windows with reduced room fill.
for o in list(bpy.data.objects):
 if o.type=="LIGHT":bpy.data.objects.remove(o,do_unlink=True)
scene.world.use_nodes=True
wn=scene.world.node_tree.nodes;wl=scene.world.node_tree.links
wn.clear();out=wn.new("ShaderNodeOutputWorld");bg=wn.new("ShaderNodeBackground");bg.inputs["Color"].default_value=(.68,.79,1,1);bg.inputs["Strength"].default_value=.10;wl.new(bg.outputs[0],out.inputs[0])
def area(name,loc,target,power,size,col):
 bpy.ops.object.light_add(type="AREA",location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape="DISK";o.data.size=size;o.data.color=col;o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler()
area("Gable daylight",(1.775,3.99,1.43),(2.7,1.4,.65),95,.90,(1,.94,.82))
area("Roof daylight",(.38,1.46,1.72),(2.6,2.9,.30),55,.65,(.84,.91,1))
area("Very soft camera fill",(2.4,.5,1.75),(2,3,1),5,1.8,(.9,.94,1))
# Cameras: reference-based estimates, no calibrated camera solve.
def camera(name,loc,target,lens):
 bpy.ops.object.camera_add(location=loc);o=bpy.context.object;o.name=name;o.data.lens=lens;o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler();return o
portrait=camera("05 Photo comparison angle",(.95,1.18,1.65),(2.08,3.26,1.30),19)
scene.camera=bpy.data.objects["01 View from entrance"]
scene.view_settings.view_transform="AgX";scene.view_settings.exposure=-.50
scene.render.engine="CYCLES";scene.cycles.samples=48;scene.cycles.use_denoising=True
gpu=False
try:
 prefs=bpy.context.preferences.addons["cycles"].preferences
 prefs.compute_device_type="OPTIX";prefs.get_devices()
 for d in prefs.devices:d.use=d.type!="CPU"
 gpu=any(d.type!="CPU" for d in prefs.devices)
 if gpu:scene.cycles.device="GPU"
except Exception as e:print("GPU fallback",e)
scene["appearance_status"]="Photo-guided materials and detail pass. Textures procedural; exterior from 2D photo reference. No calibrated photo match."
# Close the wall thickness at the left reveal; avoid a visible light leak.
gable=bpy.data.objects["Window end left"]
solid=gable.modifiers.new("Gable wall thickness","SOLIDIFY");solid.thickness=.12;solid.offset=0
# All used images packed; GLB transfers base-color textures, bump/light may differ.
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"Room-attic-v04.blend"))
# Export room only: exterior illustration excluded from portable room file.
for o in bpy.context.selected_objects:o.select_set(False)
for o in scene.objects:
 if o.type in {"MESH","CURVE"} and not o.name.startswith("Exterior"):o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/"Room-attic-v04.glb"),export_format="GLB",use_selection=True,export_cameras=False,export_lights=False)
preview="--preview" in __import__("sys").argv
if preview:
 scene.cycles.samples=16;scene.render.resolution_x=1000;scene.render.resolution_y=750
 scene.render.filepath=str(OUT/"preview.png");bpy.ops.render.render(write_still=True)
else:
 for name,filename,portraitmode in [
 ("01 View from entrance","01-interior.png",False),
 ("02 View towards door","02-door.png",False),
 ("05 Photo comparison angle","05-photo-angle.png",True)]:
  scene.camera=bpy.data.objects[name]
  scene.render.resolution_x=1050 if portraitmode else 1400
  scene.render.resolution_y=1400 if portraitmode else 1050
  scene.render.filepath=str(OUT/filename);bpy.ops.render.render(write_still=True)
(OUT/"appearance.json").write_text(json.dumps({"gpu_rendering":gpu,"textures":"procedurally generated image textures, embedded","camera":"estimated from reference images, not calibrated","exterior":"flat photo-reference backdrop; excluded from GLB","measurements":"v03 preserved; no new dimensional claims","improvements":["staggered wood flooring","wood grain textures","striped draped bedding","puffed cushions","split headboard","arched door glazing","five articulated spotlights","heater grille","window-based lighting"]},indent=2))
print("V04_DONE",gpu)



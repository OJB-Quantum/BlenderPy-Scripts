# BlenderPy-Scripts-for-Science
For visualization of imported or generated data in Blende. 

One example workflow for visualizing calculated molecular structures goes like this: calculate model >> export .mol file >> import .mol into converter (Open Babel) >> export .pdb >> import .pdb into Blender ([Atomic Blender](https://docs.blender.org/manual/en/latest/addons/import_export/mesh_atomic.html)) >> adjust model geometry attributes as needed >> configure render settings >> render >> export as video or image file. 
(Make sure that the Atomic Blender add-on is enabled under EDIT tab >> PREFERENCES so that you can import a .pdb file. Additionally, the xyz file format may be substituted in place of the pdb since Blender can accept both).

The SCRIPTING tab in Blender can be found on the upper-right-hand side of the interface. Once the tab is opened, you can load a copy of Python scripts in directly through copy-paste. It is also possible to copy the code on the left-side of the scripting interface by selecting the INFO button, pressing SELECT ALL, Ctrl + C, then Ctrl + V on the main scripting panel found directly under the SCRIPTING tab. Before running the script, be sure to check that the command "import bpy" is inserted at the top of the script. If it's not there, type it in.

Other examples simply involve generating objects like waves and vector fields and converting them into 3D meshes using the built-in Blender Python scripting environment.

Blender keeps track of all your actions in the program, so you should be able to automate any set of steps or make them repeatable and exportable by experimenting with the directions above. 

Enjoy. 

---

Also, I have a free Flickr album of some rendered objects available: <https://www.flickr.com/photos/194516106@N05/albums>

--- 

| Links to programs used in the workflow example: |
|-|
| [Avogadro2](https://github.com/openchemistry/avogadrolibs) |
| [MolView](https://molview.org) |
| [Open Babel](https://github.com/openbabel/openbabel/releases/tag/openbabel-3-1-1) |
| [Atomic Blender](https://docs.blender.org/manual/en/latest/addons/import_export/mesh_atomic.html) |

--- 

![Screenshot 2023-03-27 073147](https://user-images.githubusercontent.com/88035770/227973246-258a7ede-ee07-4eb2-80b0-53905947d27e.png)


![Screenshot 2023-03-27 091611](https://user-images.githubusercontent.com/88035770/227973274-b59f7e5b-d207-4a14-b9e3-d391de7d40d0.png)


![Screenshot 2023-03-27 091657](https://user-images.githubusercontent.com/88035770/228775472-7f24bae2-b840-4d99-af93-87f24ca062c9.png)


![Caffeine in 4K with white bkgnd (2)](https://user-images.githubusercontent.com/88035770/228815450-ed9df092-184b-4560-8de3-5a4cabe3c296.png)

![EM Waves 2K](https://github.com/user-attachments/assets/b777b243-23a1-428c-bacb-d915d4aa9093)

![Gabriel's Horn 001](https://github.com/user-attachments/assets/474cac75-fa0f-4103-9e3d-99e162b93dbe)

![414388327-6c86f859-76be-4f57-b9f8-89d89e9d2d03](https://github.com/user-attachments/assets/fa65c92f-3693-46ba-8e79-2ae78523d52e)

![Magnetic Fields from Script](https://github.com/user-attachments/assets/2d348168-bf17-4d21-b7ba-cc187686a9b5)


If you need more learning resources on using Blender for scientific purposes, view more resources on the Blender-Common-Tools repository: <https://github.com/OJB-Quantum/Blender-Common-Tools>

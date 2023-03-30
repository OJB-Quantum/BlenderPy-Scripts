# BlenderPy-Scripts-for-Science
For atomic or molecular modeling, you can use a free program like Avogadro2 or MolView for the initial computation/ extraction/ export to a .mol file that can be converted into .pdb file format by other free programs like OpenBabel. 

Example of the workflow goes like this: calculate model >> export .mol file >> import .mol into converter (OpenBabel) >> export .pdb >> import .pdb into Blender >> adjust model geometry attributes as needed >> configure render settings >> render >> export as video or image file. 
(Make sure that the Atomic Blender add-on is enabled under EDIT tab >> PREFERENCES so that you can import a .pdb file).

The SCRIPTING tab in Blender can be found on the upper-right-hand side of the interface. Once the tab is opened, you can load a copy of Python scripts in directly through copy-paste. It is also possible to copy the code on the left-side of the scripting interface by selecting the INFO button, pressing SELECT ALL, Ctrl + C, then Ctrl + V on the main scripting panel found directly under the SCRIPTING tab. Before running the script, be sure to check that the command "import bpy" is inserted at the top of the script. If it's not there, type it in.

Blender keeps track of all your actions in the program, so you should be able to automate any set of steps or make them repeatable and exportable by experimenting with the directions above. 

Enjoy. 


![Screenshot 2023-03-27 073147](https://user-images.githubusercontent.com/88035770/227973246-258a7ede-ee07-4eb2-80b0-53905947d27e.png)


![Screenshot 2023-03-27 091611](https://user-images.githubusercontent.com/88035770/227973274-b59f7e5b-d207-4a14-b9e3-d391de7d40d0.png)


![Screenshot 2023-03-27 091657](https://user-images.githubusercontent.com/88035770/228775472-7f24bae2-b840-4d99-af93-87f24ca062c9.png)


If you need more learning resources on using Blender for scientific purposes, this is a great channel to start with: https://youtu.be/gAQxwNUH3JA

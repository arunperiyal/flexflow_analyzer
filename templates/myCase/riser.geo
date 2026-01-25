cl__1 = 1;

dia = 1;

LeadingGap = 15;
TopBottomGap = 15;
TrailingGap = 25;

// Groove dimensions
d_groove = #groove_depth*dia ;
w_groove = #groove_width*dia ;
Rg = 0.5 - d_groove ;
Theta_g = Asin(w_groove/dia) ;

bLTh = 0.05*dia ;

CirclePoints = 33;
GroovePoints = 11 ;
SideGroovePoints = 11;
BoundaryLayerPoints = 37;	// Radial Boundary Layer Points
BoundaryLayerProgression = 1.23;

// Box Field Dimensions : Dynamic based on the gaps
BoxFieldXmin = (-3)*dia;
BoxFieldXmax = (12)*dia;
BoxFieldYmin = (-3)*dia;
BoxFieldYmax = (3)*dia;

MeshBoundaryTransition = 0.08;

STDSize = 1;

// Cylinder Inner Points
Point(newp) = {0, 0, 0, STDSize};

// Cylinder Outer Points
//Point(10) = {BoundaryExpansion*dia*Cos(1*Pi/4)/2, BoundaryExpansion*dia*Sin(1*Pi/4)/2, 0, STDSize};
//Point(11) = {BoundaryExpansion*dia*Cos(3*Pi/4)/2, BoundaryExpansion*dia*Sin(3*Pi/4)/2, 0, STDSize};
//Point(12) = {BoundaryExpansion*dia*Cos(5*Pi/4)/2, BoundaryExpansion*dia*Sin(5*Pi/4)/2, 0, STDSize};
//Point(13) = {BoundaryExpansion*dia*Cos(7*Pi/4)/2, BoundaryExpansion*dia*Sin(7*Pi/4)/2, 0, STDSize};


// Domain Boundaries
Point(newp) = {-LeadingGap*dia, TopBottomGap*dia, 0, STDSize};
Point(newp) = {-LeadingGap*dia, -TopBottomGap*dia, 0, STDSize};
Point(newp) = {TrailingGap*dia, -TopBottomGap*dia, 0, STDSize};
Point(newp) = {TrailingGap*dia, TopBottomGap*dia, 0, STDSize};

// Groove points
// Right point
Point(newp) = {(dia/2)*Cos(Theta_g), (dia/2)*Sin(Theta_g), 0, STDSize};
Point(newp) = {Rg*Cos(Theta_g), Rg*Sin(Theta_g), 0,STDSize};
Point(newp) = {(dia/2)*Cos(Theta_g), -(dia/2)*Sin(Theta_g), 0, STDSize};
Point(newp) = {Rg*Cos(Theta_g), -Rg*Sin(Theta_g), 0,STDSize};

Point(newp) = {(dia/2+bLTh)*Cos(Theta_g/2), (dia/2+bLTh)*Sin(Theta_g/2), 0, STDSize};
Point(newp) = {(Rg+bLTh)*Cos(Theta_g/2), (Rg+bLTh)*Sin(Theta_g/2), 0,STDSize};
Point(newp) = {(dia/2+bLTh)*Cos(Theta_g/2), -(dia/2+bLTh)*Sin(Theta_g/2), 0, STDSize};
Point(newp) = {(Rg+bLTh)*Cos(Theta_g/2), -(Rg+bLTh)*Sin(Theta_g/2), 0,STDSize};

// Bottom point
Point(newp) = {(dia/2)*Sin(Theta_g), -(dia/2)*Cos(Theta_g), 0, STDSize};
Point(newp) = {Rg*Sin(Theta_g), -Rg*Cos(Theta_g), 0,STDSize};
Point(newp) = {-(dia/2)*Sin(Theta_g), -(dia/2)*Cos(Theta_g), 0, STDSize};
Point(newp) = {-Rg*Sin(Theta_g), -Rg*Cos(Theta_g), 0,STDSize};

Point(newp) = {(dia/2+bLTh)*Sin(Theta_g/2), -(dia/2+bLTh)*Cos(Theta_g/2), 0, STDSize};
Point(newp) = {(Rg+bLTh)*Sin(Theta_g/2), -(Rg+bLTh)*Cos(Theta_g/2), 0,STDSize};
Point(newp) = {-(dia/2+bLTh)*Sin(Theta_g/2), -(dia/2+bLTh)*Cos(Theta_g/2), 0, STDSize};
Point(newp) = {-(Rg+bLTh)*Sin(Theta_g/2), -(Rg+bLTh)*Cos(Theta_g/2), 0,STDSize};

// Left point
Point(newp) = {-(dia/2)*Cos(Theta_g), (dia/2)*Sin(Theta_g), 0, STDSize};
Point(newp) = {-Rg*Cos(Theta_g), Rg*Sin(Theta_g), 0,STDSize};
Point(newp) = {-(dia/2)*Cos(Theta_g), -(dia/2)*Sin(Theta_g), 0, STDSize};
Point(newp) = {-Rg*Cos(Theta_g), -Rg*Sin(Theta_g), 0,STDSize};

Point(newp) = {-(dia/2+bLTh)*Cos(Theta_g/2), (dia/2+bLTh)*Sin(Theta_g/2), 0, STDSize};
Point(newp) = {-(Rg+bLTh)*Cos(Theta_g/2), (Rg+bLTh)*Sin(Theta_g/2), 0,STDSize};
Point(newp) = {-(dia/2+bLTh)*Cos(Theta_g/2), -(dia/2+bLTh)*Sin(Theta_g/2), 0, STDSize};
Point(newp) = {-(Rg+bLTh)*Cos(Theta_g/2), -(Rg+bLTh)*Sin(Theta_g/2), 0,STDSize};

// Top point
Point(newp) = {(dia/2)*Sin(Theta_g), (dia/2)*Cos(Theta_g), 0, STDSize};
Point(newp) = {Rg*Sin(Theta_g), Rg*Cos(Theta_g), 0,STDSize};
Point(newp) = {-(dia/2)*Sin(Theta_g), (dia/2)*Cos(Theta_g), 0, STDSize};
Point(newp) = {-Rg*Sin(Theta_g), Rg*Cos(Theta_g), 0,STDSize};

Point(newp) = {(dia/2+bLTh)*Sin(Theta_g/2), (dia/2+bLTh)*Cos(Theta_g/2), 0, STDSize};
Point(newp) = {(Rg+bLTh)*Sin(Theta_g/2), (Rg+bLTh)*Cos(Theta_g/2), 0,STDSize};
Point(newp) = {-(dia/2+bLTh)*Sin(Theta_g/2), (dia/2+bLTh)*Cos(Theta_g/2), 0, STDSize};
Point(newp) = {-(Rg+bLTh)*Sin(Theta_g/2), (Rg+bLTh)*Cos(Theta_g/2), 0,STDSize};



// Transfinite Surface and Lines
//Transfinite Line {6, 7, 8, 9, 10, 11, 12, 13} = CirclePoints Using Progression 1;
//Transfinite Line {-14, -15, 16, 17} = BoundaryLayerPoints Using Progression BoundaryLayerProgression;



// Box Field
Field[1] = Box;
Field[1].VIn = MeshBoundaryTransition;
Field[1].VOut = 1;
Field[1].XMax = 0.001;
Field[1].XMin = -0.001;
Field[1].YMax = BoxFieldYmax;
Field[1].YMin = BoxFieldYmin;
Field[1].ZMax = BoxFieldXmax;
Field[1].ZMin = BoxFieldXmin;


//Frustum Upper
Field[3] = Frustum;
Field[3].R1_inner = 0;
Field[3].R1_outer = (BoxFieldXmax - BoxFieldXmin)/2;
Field[3].R2_inner = 0;
Field[3].R2_outer = (BoxFieldXmax - BoxFieldXmin)/2;
Field[3].V1_inner = MeshBoundaryTransition;
Field[3].V1_outer = MeshBoundaryTransition;
Field[3].V2_inner = 1;
Field[3].V2_outer = 1;
Field[3].X1 = 0;
Field[3].X2 = 0;
Field[3].Y1 = BoxFieldYmax;
Field[3].Y2 = TopBottomGap;
Field[3].Z1 = (BoxFieldXmin+BoxFieldXmax)/2;
Field[3].Z2 = (BoxFieldXmin+BoxFieldXmax)/2;

//Frustum Lower
Field[4] = Frustum;
Field[4].R1_inner = 0;
Field[4].R1_outer = (BoxFieldXmax - BoxFieldXmin)/2;
Field[4].R2_inner = 0;
Field[4].R2_outer = (BoxFieldXmax - BoxFieldXmin)/2;
Field[4].V1_inner = MeshBoundaryTransition;
Field[4].V1_outer = MeshBoundaryTransition;
Field[4].V2_inner = 1;
Field[4].V2_outer = 1;
Field[4].X1 = 0;
Field[4].X2 = 0;
Field[4].Y1 = -BoxFieldYmax;
Field[4].Y2 = -TopBottomGap;
Field[4].Z1 = (BoxFieldXmin+BoxFieldXmax)/2;
Field[4].Z2 = (BoxFieldXmin+BoxFieldXmax)/2;

//Frustum Left
Field[5] = Frustum;
Field[5].R1_inner = 0;
Field[5].R1_outer = (LeadingGap*dia+BoxFieldXmin);
Field[5].R2_inner = 0;
Field[5].R2_outer = (LeadingGap*dia+BoxFieldXmin);
Field[5].V1_inner = MeshBoundaryTransition;
Field[5].V1_outer = 1;
Field[5].V2_inner = MeshBoundaryTransition;
Field[5].V2_outer = 1;
Field[5].X1 = 0;
Field[5].X2 = 0;
Field[5].Y1 = BoxFieldYmin;
Field[5].Y2 = BoxFieldYmax;
Field[5].Z1 = BoxFieldXmin;
Field[5].Z2 = BoxFieldXmin;

//Frustum Right
Field[6] = Frustum;
Field[6].R1_inner = 0;
Field[6].R1_outer = (TrailingGap*dia+BoxFieldXmax);
Field[6].R2_inner = 0;
Field[6].R2_outer = (TrailingGap*dia+BoxFieldXmax);
Field[6].V1_inner = MeshBoundaryTransition;
Field[6].V1_outer = 1;
Field[6].V2_inner = MeshBoundaryTransition;
Field[6].V2_outer = 1;
Field[6].X1 = 0;
Field[6].X2 = 0;
Field[6].Y1 = BoxFieldYmin;
Field[6].Y2 = BoxFieldYmax;
Field[6].Z1 = BoxFieldXmax;
Field[6].Z2 = BoxFieldXmax;

//Frustum Corner Top Left
Field[7] = Frustum;
Field[7].R1_inner = 0;
Field[7].R1_outer = (LeadingGap*dia+BoxFieldXmin);
Field[7].R2_inner = 0;
Field[7].R2_outer = (LeadingGap*dia+BoxFieldXmin);
Field[7].V1_inner = MeshBoundaryTransition;
Field[7].V1_outer = 1;
Field[7].V2_inner = 1;
Field[7].V2_outer = 1;
Field[7].X1 = 0;
Field[7].X2 = 0;
Field[7].Y1 = BoxFieldYmax;
Field[7].Y2 = TopBottomGap;
Field[7].Z1 = BoxFieldXmin;
Field[7].Z2 = BoxFieldXmin;

//Frustum Corner Bottom Left
Field[8] = Frustum;
Field[8].R1_inner = 0;
Field[8].R1_outer = (LeadingGap*dia+BoxFieldXmin);
Field[8].R2_inner = 0;
Field[8].R2_outer = (LeadingGap*dia+BoxFieldXmin);
Field[8].V1_inner = MeshBoundaryTransition;
Field[8].V1_outer = 1;
Field[8].V2_inner = 1;
Field[8].V2_outer = 1;
Field[8].X1 = 0;
Field[8].X2 = 0;
Field[8].Y1 = -BoxFieldYmax;
Field[8].Y2 = -TopBottomGap;
Field[8].Z1 = BoxFieldXmin;
Field[8].Z2 = BoxFieldXmin;

//Frustum Corner Top Right
Field[9] = Frustum;
Field[9].R1_inner = 0;
Field[9].R1_outer = (TrailingGap*dia+BoxFieldXmax);
Field[9].R2_inner = 0;
Field[9].R2_outer = (TrailingGap*dia+BoxFieldXmax);
Field[9].V1_inner = MeshBoundaryTransition;
Field[9].V1_outer = 1;
Field[9].V2_inner = 1;
Field[9].V2_outer = 1;
Field[9].X1 = 0;
Field[9].X2 = 0;
Field[9].Y1 = BoxFieldYmax;
Field[9].Y2 = TopBottomGap;
Field[9].Z1 = BoxFieldXmax;
Field[9].Z2 = BoxFieldXmax;

//Frustum Corner Bottom Right
Field[10] = Frustum;
Field[10].R1_inner = 0;
Field[10].R1_outer = (TrailingGap*dia+BoxFieldXmax);
Field[10].R2_inner = 0;
Field[10].R2_outer = (TrailingGap*dia+BoxFieldXmax);
Field[10].V1_inner = MeshBoundaryTransition;
Field[10].V1_outer = 1;
Field[10].V2_inner = 1;
Field[10].V2_outer = 1;
Field[10].X1 = 0;
Field[10].X2 = 0;
Field[10].Y1 = -BoxFieldYmax;
Field[10].Y2 = -TopBottomGap;
Field[10].Z1 = BoxFieldXmax;
Field[10].Z2 = BoxFieldXmax;

// Min Field
Field[2] = Min;
Field[2].FieldsList = {1, 3, 4, 5, 6, 7, 8, 9, 10};
Background Field = 2;
Recombine Surface {28};


//Mesh.Algorithm = 5;

Mesh.Format = 1; 
Mesh.MshFileVersion = 2.2;

//+
Circle(1) = {30, 1, 6};
//+
Circle(2) = {7, 1, 9};
//+
Circle(3) = {8, 1, 14};
//+
Circle(4) = {15, 1, 17};
//+
Circle(5) = {16, 1, 24};
//+
Circle(6) = {25, 1, 23};
//+
Circle(7) = {22, 1, 32};
//+
Circle(8) = {33, 1, 31};
//+
Circle(9) = {11, 1, 13};
//+
Circle(10) = {19, 1, 21};
//+
Circle(11) = {29, 1, 27};
//+
Circle(12) = {33, 1, 31};
//+
Circle(13) = {37, 1, 35};
//+
Circle(14) = {34, 1, 10};
//+
Circle(15) = {12, 1, 18};
//+
Circle(16) = {20, 1, 28};
//+
Circle(17) = {26, 1, 36};
//+
Line(18) = {36, 37};
//+
Line(19) = {32, 33};
//+
Line(20) = {35, 34};
//+
Line(21) = {31, 30};
//+
Line(22) = {6, 7};
//+
Line(23) = {11, 10};
//+
Line(24) = {13, 12};
//+
Line(25) = {9, 8};
//+
Line(26) = {15, 14};
//+
Line(27) = {19, 18};
//+
Line(28) = {21, 20};
//+
Line(29) = {17, 16};
//+
Line(30) = {25, 24};
//+
Line(31) = {29, 28};
//+
Line(32) = {27, 26};
//+
Line(33) = {22, 23};
//+
Line(34) = {35, 31};
//+
Line(35) = {34, 30};
//+
Line(36) = {37, 33};
//+
Line(37) = {36, 32};
//+
Line(38) = {27, 23};
//+
Line(39) = {22, 26};
//+
Line(40) = {29, 25};
//+
Line(41) = {28, 24};
//+
Line(42) = {17, 21};
//+
Line(43) = {15, 19};
//+
Line(44) = {16, 20};
//+
Line(45) = {14, 18};
//+
Line(46) = {8, 12};
//+
Line(47) = {13, 9};
//+
Line(48) = {7, 11};
//+
Line(49) = {6, 10};
//+
Transfinite Curve {-41, -40, -38, 39, -37, -36, -34, -35, 49, 48, -47, 46, 45, 43, 42, 44} = BoundaryLayerPoints Using Progression BoundaryLayerProgression;
//+
Transfinite Curve {7, 1, 3, 5, 17, 14, 15, 16} = CirclePoints Using Progression 1;
//+
Transfinite Curve {11, 6, 13, 8, 4, 10, 2, 9} = GroovePoints Using Progression 1;
//+
Transfinite Curve {32, 33, 31, 30, 19, 18, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29} = SideGroovePoints Using Progression 1;
//+
Curve Loop(1) = {17, 37, -7, 39};
//+
Plane Surface(1) = {1};
//+
Curve Loop(2) = {37, 19, -36, -18};
//+
Plane Surface(2) = {2};
//+
Curve Loop(3) = {13, 34, -8, -36};
//+
Plane Surface(3) = {3};
//+
Curve Loop(4) = {21, -35, -20, 34};
//+
Plane Surface(4) = {4};
//+
Curve Loop(5) = {1, 49, -14, 35};
//+
Plane Surface(5) = {5};
//+
Curve Loop(6) = {49, -23, -48, -22};
//+
Plane Surface(6) = {6};
//+
Curve Loop(7) = {48, 9, 47, -2};
//+
Plane Surface(7) = {7};
//+
Curve Loop(8) = {47, 25, 46, -24};
//+
Plane Surface(8) = {8};
//+
Curve Loop(9) = {46, 15, -45, -3};
//+
Plane Surface(9) = {9};
//+
Curve Loop(10) = {26, 45, -27, -43};
//+
Plane Surface(10) = {10};
//+
Curve Loop(11) = {4, 42, -10, -43};
//+
Plane Surface(11) = {11};
//+
Curve Loop(12) = {42, 28, -44, -29};
//+
Plane Surface(12) = {12};
//+
Curve Loop(13) = {5, -41, -16, -44};
//+
Plane Surface(13) = {13};
//+
Curve Loop(14) = {31, 41, -30, -40};
//+
Plane Surface(14) = {14};
//+
Curve Loop(15) = {40, 6, -38, -11};
//+
Plane Surface(15) = {15};
//+
Curve Loop(16) = {32, -39, 33, -38};
//+
Plane Surface(16) = {16};

Transfinite Surface "*";

//+
Line(50) = {2, 5};
//+
Line(51) = {5, 4};
//+
Line(52) = {4, 3};
//+
Line(53) = {3, 2};
//+
Curve Loop(17) = {53, 50, 51, 52};
//+

//+
//+
Circle(54) = {36, 1, 34};
//+
Circle(55) = {10, 1, 12};
//+
Circle(56) = {18, 1, 20};
//+
Circle(57) = {28, 1, 26};
//+
Curve Loop(19) = {18, 13, 20, -54};
//+
Plane Surface(18) = {19};
//+
Curve Loop(20) = {32, -57, -31, 11};
//+
Plane Surface(19) = {20};
//+
Curve Loop(21) = {10, 28, -56, -27};
//+
Plane Surface(20) = {21};
//+
Curve Loop(22) = {24, -55, -23, 9};
//+
Plane Surface(21) = {22};
//+
Transfinite Curve {54, 55, 57, 56} = GroovePoints Using Progression 1;
Transfinite Surface "*";
//Recombine Surface "*";
//+
Rotate {{0, 1, 0}, {0, 0, 0}, -Pi/2} {
  Point{2}; Point{5}; Point{36}; Point{34}; Point{32}; Point{37}; Point{30}; Point{35}; Point{33}; Point{31}; Point{22}; Point{23}; Point{26}; Point{27}; Point{28}; Point{29}; Point{6}; Point{7}; Point{1}; Point{25}; Point{24}; Point{11}; Point{10}; Point{13}; Point{12}; Point{9}; Point{8}; Point{17}; Point{15}; Point{21}; Point{16}; Point{19}; Point{14}; Point{20}; Point{18}; Point{3}; Point{4}; Curve{50}; Curve{54}; Curve{37}; Curve{18}; Curve{35}; Curve{20}; Curve{13}; Curve{19}; Curve{36}; Curve{34}; Curve{12}; Curve{8}; Curve{21}; Curve{7}; Curve{33}; Curve{17}; Curve{39}; Curve{38}; Curve{32}; Curve{57}; Curve{11}; Curve{31}; Curve{1}; Curve{22}; Curve{40}; Curve{6}; Curve{41}; Curve{30}; Curve{48}; Curve{14}; Curve{49}; Curve{23}; Curve{9}; Curve{24}; Curve{55}; Curve{2}; Curve{47}; Curve{46}; Curve{25}; Curve{4}; Curve{42}; Curve{5}; Curve{29}; Curve{10}; Curve{43}; Curve{26}; Curve{3}; Curve{28}; Curve{16}; Curve{44}; Curve{56}; Curve{27}; Curve{45}; Curve{15}; Curve{53}; Curve{52}; Curve{51}; Surface{18}; Surface{2}; Surface{3}; Surface{4}; Surface{1}; Surface{5}; Surface{16}; Surface{19}; Surface{15}; Surface{14}; Surface{6}; Surface{7}; Surface{21}; Surface{8}; Surface{13}; Surface{11}; Surface{12}; Surface{9}; Surface{10}; Surface{20}; 
}





//+
/*Physical Volume("fluid") = {22, 21, 20, 19, 17, 15, 18, 14, 13, 12, 16, 1, 9, 11, 10, 8, 6, 7, 5, 2, 4, 3};
Physical Surface("inlet") = {986};
Physical Surface("outlet") = {987};
Physical Surface("top") = {988};
Physical Surface("bottom") = {989};
Physical Surface("side1") = {23, 22, 5, 4, 3, 18, 2, 1, 16, 15, 19, 14, 13, 6, 7, 21, 8, 9, 12, 11, 20, 10};
Physical Surface("side2") = {545, 990, 875, 765, 743, 699, 677, 589, 611, 633, 567, 655, 721, 919, 897, 941, 963, 985, 787, 831, 809, 853};
Physical Surface("cyl") = {892, 950, 910, 972, 870, 760, 734, 672, 576, 610, 620, 642, 720, 852, 808, 778};
Physical Volume("cyl_BL") = {16, 18, 17, 20, 19, 21, 11, 8, 7, 10, 3, 4, 5, 2, 6, 9, 12, 14, 13, 15};
Physical Curve("cyl_nodes") = {887};*/

//+
Curve Loop(23) = {17, 54, 14, 55, 15, 56, 16, 57};
//+
Plane Surface(22) = {17, 23};
//+
Recombine Surface "*";

Extrude {12, 0, 0} {
  Surface{22}; Surface{20}; Surface{12}; Surface{10}; Surface{11}; Surface{13}; Surface{9}; Surface{14}; Surface{8}; Surface{19}; Surface{15}; Surface{16}; Surface{21}; Surface{7}; Surface{6}; Surface{1}; Surface{3}; Surface{5}; Surface{2}; Surface{4}; Surface{18}; 
  Layers {48}; 
  Recombine;
}
//+
Physical Volume("fluid") = {16, 19, 21, 12, 10, 17, 20, 11, 8, 18, 6, 15, 14, 3, 5, 13, 9, 2, 4, 7, 1};
Physical Surface("inlet") = {74};
Physical Surface("outlet") = {82};
Physical Surface("top") = {86};
Physical Surface("bottom") = {78};
Physical Surface("side1") = {119, 229, 141, 163, 207, 185, 251, 383, 295, 405, 427, 493, 537, 471, 559, 515, 449, 361, 339, 317, 273};
Physical Surface("side2") = {22, 16, 19, 15, 14, 13, 1, 18, 2, 3, 4, 5, 6, 21, 7, 8, 9, 11, 10, 20, 12};
Physical Surface("cyl") = {250, 172, 194, 162, 216, 286, 404, 426, 480, 524, 466, 506, 444, 356, 330, 268};
Physical Curve("cyl_nodes") = {390};
Physical Volume("cyl_BL") = {2, 4, 7, 5, 3, 9, 13, 14, 6, 15, 8, 18, 11, 10, 12, 16, 17, 20, 19, 21};
//+
Rotate {{1, 0, 0}, {0, 0, 0}, Pi/4} {
  Point{26}; Point{22}; Point{28}; Point{27}; Point{23}; Point{29}; Point{24}; Point{32}; Point{36}; Point{25}; Point{33}; Point{37}; Point{34}; Point{35}; Point{30}; Point{31}; Point{1}; Point{17}; Point{16}; Point{21}; Point{20}; Point{19}; Point{15}; Point{7}; Point{18}; Point{14}; Point{6}; Point{11}; Point{9}; Point{13}; Point{10}; Point{8}; Point{12}; Point{54}; Point{131}; Point{56}; Point{118}; Point{125}; Point{106}; Point{104}; Point{151}; Point{86}; Point{115}; Point{163}; Point{152}; Point{81}; Point{154}; Point{164}; Point{158}; Point{55}; Point{90}; Point{99}; Point{89}; Point{61}; Point{87}; Point{100}; Point{143}; Point{66}; Point{101}; Point{144}; Point{142}; Point{117}; Point{116}; Point{76}; Point{105}; Point{71}; Curve{39}; Curve{57}; Curve{32}; Curve{33}; Curve{38}; Curve{31}; Curve{11}; Curve{41}; Curve{7}; Curve{17}; Curve{37}; Curve{40}; Curve{30}; Curve{6}; Curve{19}; Curve{36}; Curve{18}; Curve{54}; Curve{20}; Curve{13}; Curve{35}; Curve{34}; Curve{8}; Curve{21}; Curve{5}; Curve{29}; Curve{42}; Curve{28}; Curve{44}; Curve{16}; Curve{10}; Curve{43}; Curve{4}; Curve{27}; Curve{56}; Curve{26}; Curve{45}; Curve{22}; Curve{1}; Curve{48}; Curve{2}; Curve{47}; Curve{9}; Curve{49}; Curve{14}; Curve{23}; Curve{25}; Curve{55}; Curve{46}; Curve{24}; Curve{3}; Curve{15}; Curve{88}; Curve{351}; Curve{342}; Curve{63}; Curve{89}; Curve{302}; Curve{297}; Curve{329}; Curve{343}; Curve{321}; Curve{258}; Curve{253}; Curve{300}; Curve{210}; Curve{215}; Curve{431}; Curve{439}; Curve{430}; Curve{70}; Curve{113}; Curve{255}; Curve{256}; Curve{267}; Curve{320}; Curve{496}; Curve{465}; Curve{498}; Curve{456}; Curve{454}; Curve{109}; Curve{69}; Curve{451}; Curve{457}; Curve{519}; Curve{478}; Curve{476}; Curve{517}; Curve{452}; Curve{453}; Curve{461}; Curve{148}; Curve{157}; Curve{146}; Curve{209}; Curve{143}; Curve{127}; Curve{64}; Curve{145}; Curve{122}; Curve{93}; Curve{121}; Curve{126}; Curve{170}; Curve{187}; Curve{168}; Curve{390}; Curve{124}; Curve{97}; Curve{65}; Curve{165}; Curve{171}; Curve{166}; Curve{412}; Curve{473}; Curve{410}; Curve{385}; Curve{377}; Curve{388}; Curve{281}; Curve{366}; Curve{280}; Curve{275}; Curve{365}; Curve{407}; Curve{105}; Curve{68}; Curve{276}; Curve{236}; Curve{101}; Curve{231}; Curve{278}; Curve{67}; Curve{234}; Curve{66}; 
}

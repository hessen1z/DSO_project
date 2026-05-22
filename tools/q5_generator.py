import os
import cv2
import numpy as np

def generate_q5_map():
    # Make maps folder if not exist
    os.makedirs(os.path.join("config", "maps"), exist_ok=True)
    
    # 800x600 dark canvas
    h, w = 600, 800
    img = np.zeros((h, w, 3), dtype=np.uint8)
    
    # Fill with deep dark grey
    img[:] = (18, 18, 22)
    
    # Draw subtle tech grid
    grid_color = (28, 28, 35)
    for x in range(0, w, 40):
        cv2.line(img, (x, 0), (x, h), grid_color, 1)
    for y in range(0, h, 40):
        cv2.line(img, (0, y), (w, y), grid_color, 1)
        
    # Draw glowing layout
    # Create separate layer for the transparent map corridors
    map_layer = np.zeros_like(img)
    
    # Define map layout nodes
    # Entrance
    n_entrance = (100, 480)
    n_entrance_branch = (70, 520)
    
    # Left corridor to junction
    n_junc1 = (220, 360)
    n_junc_up_left = (180, 240)
    
    # Top-right loop path
    n_top_mid = (380, 280)
    n_top_room = (480, 100)
    n_top_loop_exit = (550, 250)
    
    # Bottom loop path
    n_bottom_mid = (400, 500)
    n_bottom_room = (580, 460)
    
    # Right intersection/room
    n_right_room = (680, 380)
    n_right_branch = (760, 420)
    
    # Connect pathways
    pathways = [
        # Main entrance
        (n_entrance_branch, n_entrance),
        (n_entrance, n_junc1),
        (n_junc1, n_junc_up_left),
        
        # Upper branch
        (n_junc1, n_top_mid),
        (n_top_mid, n_top_room),
        (n_top_room, n_top_loop_exit),
        
        # Lower branch
        (n_entrance, n_bottom_mid),
        (n_bottom_mid, n_bottom_room),
        
        # Loop merging to right room
        (n_top_loop_exit, n_right_room),
        (n_bottom_room, n_right_room),
        (n_right_room, n_right_branch)
    ]
    
    # Draw pathways as thick transparent grey corridors
    for pt1, pt2 in pathways:
        cv2.line(map_layer, pt1, pt2, (100, 100, 110), 36)
        
    # Draw some custom room-like shapes (polygons/circles) at the ends
    cv2.circle(map_layer, n_top_room, 30, (100, 100, 110), -1)
    cv2.circle(map_layer, n_right_room, 35, (100, 100, 110), -1)
    cv2.circle(map_layer, n_entrance, 25, (100, 100, 110), -1)
    
    # Combine original and map layer with alpha blending
    # This simulates the semi-transparent game overlay map
    alpha = 0.45
    cv2.addWeighted(map_layer, alpha, img, 1 - alpha, 0, img)
    
    # Now draw thin bright cyan outline borders for the corridors to make it look techy and high-end
    border_layer = np.zeros_like(map_layer)
    for pt1, pt2 in pathways:
        cv2.line(border_layer, pt1, pt2, (255, 255, 255), 38)
    cv2.circle(border_layer, n_top_room, 31, (255, 255, 255), -1)
    cv2.circle(border_layer, n_right_room, 36, (255, 255, 255), -1)
    cv2.circle(border_layer, n_entrance, 26, (255, 255, 255), -1)
    
    # Get contours of the white layout to draw the cyan outlines
    grey_border = cv2.cvtColor(border_layer, cv2.COLOR_BGR2GRAY)
    contours, _ = cv2.findContours(grey_border, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Draw contours as cyan neon glow
    cv2.drawContours(img, contours, -1, (220, 200, 180), 2, lineType=cv2.LINE_AA)
    
    # Add a glowing overlay for the start point
    cv2.circle(img, n_entrance, 6, (0, 255, 0), -1) # Green player dot replica
    cv2.circle(img, n_entrance, 12, (0, 255, 0), 2, lineType=cv2.LINE_AA) # Green glow circle
    
    # Typography: Title & Header in neon styling
    # Border card around title
    cv2.rectangle(img, (20, 20), (320, 75), (28, 28, 35), -1)
    cv2.rectangle(img, (20, 20), (320, 75), (200, 60, 60), 1)
    
    cv2.putText(img, "MAP: Q5 (LIASTANO CAVE)", (35, 45), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 250), 2, lineType=cv2.LINE_AA)
    cv2.putText(img, "DSO ELITE NAVIGATION PATH", (35, 63), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 60, 60), 1, lineType=cv2.LINE_AA)
                
    # Compass / Tech info in bottom-left
    cv2.putText(img, "RESOLUTION: 1920x1080 MAPPED", (30, h - 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 110), 1, lineType=cv2.LINE_AA)
    cv2.putText(img, "SYS STATUS: SECURE LINK", (30, h - 15), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 110), 1, lineType=cv2.LINE_AA)
                
    # Save the generated premium map image
    output_path = os.path.join("config", "maps", "q5.png")
    cv2.imwrite(output_path, img)
    print(f"Successfully generated glowing Q5 minimap at: {output_path}")

if __name__ == "__main__":
    generate_q5_map()

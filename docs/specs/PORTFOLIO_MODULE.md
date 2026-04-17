# Portfolio Module Settings: General Tab Specification

## Overview
This document specifies the configuration fields for the **General** tab of the **Portfolio Module Settings** page.
This page is used by administrators to configure how the Portfolio module behaves, specifically defining the types of portfolios (Clients vs. Internal Divisions) the system supports.

## scope
The **General** tab focuses on high-level module definition, identity, and core structural behavior.
It excludes:
- Detailed Field Management (Handled in "Fields" tab).
- Form Layouts (Handled in "Input Forms" tab).

---

## 1. General Tab Structure

The General tab is divided into logical sections to control the module's identity and enabled features.

### 1.1 Section: General Information
*Controls how the module is named and described across the application.*

| Field Label | System Name | Data Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Module Name (Singular)** | `module_name_singular` | String | "Portfolio" | The label used for a single item (e.g., "Client", "Account"). |
| **Module Name (Plural)** | `module_name_plural` | String | "Portfolios" | The label used for the list/module (e.g., "Clients", "Accounts"). |
| **Module Description** | `module_description` | Text | [Default Text] | Brief description shown in the module header. |

### 1.2 Section: Numbering & Display Defaults
*Sets global defaults for ID generation and viewing.*

| Field Label | System Name | Data Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| **ID Generation Mode** | `id_mode` | Enum | "Default" | **Default Prefix**: Uses a fixed 3-letter prefix (e.g., "PRT").<br>**Name Based**: Uses first 3 letters of Portfolio Name (e.g., "Global" -> "GLO"). |
| **Default Prefix** | `default_prefix` | String (3 chars) | "PRT" | Fixed 3-letter prefix used if Mode="Default" or Name is too short. |

## 2. Fields Tab

The Fields tab allows administrators to manage the data points collected for a Portfolio. It uses a standard Data Grid to list both system-defined (default) fields and user-defined (custom) fields.

### 2.1 Fields Data Grid

The core of this tab is a data grid displaying all configured fields. 

#### Grid Columns

| Column Header | Data Type | Description |
| :--- | :--- | :--- |
| **Field Name** | String | The display label of the field (e.g., "Industry", "Billing ID"). |
| **System Name** | String | The internal identifier (e.g., `industry`, `custom_billing_id`). |
| **Field Type** | Enum | The data type (Text, Number, Date, Boolean, Dropdown). |
| **Order** | Number | The sort index determining the field's position on the creation form. |
| **Required** | Boolean | Whether the field is mandatory during creation. |
| **Show on Card** | Boolean | Toggle: If true, this field's value is displayed on the Portfolio summary card (underneath the Portfolio Name). |
| **Status** | Enum | `Active` or `Inactive`. Inactive fields are hidden from forms. |
| **Origin** | Enum (Read-only) | `System` (Default fields) or `Custom` (User-added). |
| **Actions** | Menu | Edit / Delete (Delete disabled for `System` origin). |

#### Default Fields (System Origin)
*These fields are locked and cannot be deleted, but some properties (like "Show on Card") can be toggled.*

1.  **Portfolio Name** (Type: String, Required: Yes, Show on Card: Yes - Locked)
2.  **Portfolio Code** (Type: String, Required: Yes, Show on Card: Yes)
3.  **Status** (Type: Enum, Required: Yes, Show on Card: No)
4.  **Description** (Type: Text, Required: No, Show on Card: No)

### 2.2 Adding/Editing a Custom Field

When a user clicks "Add Field" or "Edit" (on a custom field), a modal or side-panel opens with the following inputs:

| Input Label | Input Type | Description |
| :--- | :--- | :--- |
| **Field Name** | Text Input | The label visible to end-users on the form. |
| **System Name** | Text Input | Auto-generated from Field Name (slugified), but editable before first save. Uneditable after creation to preserve data integrity. |
| **Data Type** | Dropdown | Text, Long Text, Number, Date, Checkbox, Dropdown. |
| **Options** | dynamic list | *Conditional.* Only visible if Data Type is "Dropdown". Allows adding valid selection values. |
| **Is Required?** | Checkbox | Makes the field mandatory. |
| **Display on Card?** | Checkbox | Includes the value on the main Portfolio card view. |
| **Active** | Toggle | Determines if the field is currently in use. |

### 2.3 Interactions & Rules
-   **System Fields**: The "Delete" action is completely removed or disabled. "System Name", "Data Type", and "Origin" are read-only.
-   **Max Card Fields**: A validation rule should limit the number of fields with "Show on Card" set to True (e.g., max 3) to prevent UI clutter on the card view.
-   **Custom Field Prefix**: Custom `System Name` values should automatically be saved with a prefix (e.g., `cf_`) to avoid collisions with future system fields.
-   **Form Rendering**: The Portfolio Creation/Edit form dynamically renders all `Active` fields, sorted by the `Order` column. System fields are displayed first, followed by custom fields.

---

## 3. Users Tab

The Users tab manages which organizational users have access to configure or interact with the Portfolio Module as a whole.

*Note: This controls Module-level access (e.g., who can edit these settings or see all portfolios) rather than access to a single specific portfolio instance.*

### 3.1 Assigned Users Data Grid

Displays the users explicitly granted permissions within the Portfolio Module.

| Column Header | Data Type | Description |
| :--- | :--- | :--- |
| **User Name** | String | Full name of the user. |
| **Email** | String | Email address of the user. |
| **Module Role** | Enum | The permission level granted within this module (e.g., Module Admin, Creator, Viewer). |
| **Added On** | Date | When the user was assigned to this module. |
| **Actions** | Menu | Edit Role / Remove Selection. |

### 3.2 Adding a User Configuration

When an administrator clicks "Assign User", a modal allows them to select a user and grant module-specific permissions:

| Input Label | Input Type | Description |
| :--- | :--- | :--- |
| **Select User** | Dropdown | Select an active user from the organization. |
| **Module Role** | Dropdown | **Module Admin**: Full control over Settings (General, Fields, Users).<br>**Creator**: Can create, edit, and delete Portfolio records.<br>**Viewer**: Can only view Portfolio records globally. |

*Global "Company Admins" automatically have implicit "Module Admin" rights and do not need to be manually assigned here unless explicitly overriding behavior is required.*
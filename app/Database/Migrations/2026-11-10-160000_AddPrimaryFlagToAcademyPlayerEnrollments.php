<?php

namespace App\Database\Migrations;

use CodeIgniter\Database\Migration;

class AddPrimaryFlagToAcademyPlayerEnrollments extends Migration
{
    public function up()
    {
        $table = 'academy_player_enrollments';
        if (!$this->db->fieldExists('is_primary', $table)) {
            $this->forge->addColumn($table, [
                'is_primary' => [
                    'type' => 'TINYINT',
                    'constraint' => 1,
                    'null' => false,
                    'default' => 0,
                ],
            ]);
        }
    }

    public function down()
    {
        // Keep the column and its data. Some installations already had it.
    }
}

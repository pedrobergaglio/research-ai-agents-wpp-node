import { createBot, createProvider, createFlow, addKeyword, utils, EVENTS } from '@builderbot/bot'
import { MysqlAdapter as Database } from '@builderbot/database-mysql'
import { MetaProvider as Provider } from '@builderbot/provider-meta'
import mysql from 'mysql2/promise';
import * as fs from 'fs';
import csv from 'csv-parser';

const credentials = {
    host: process.env.MYSQL_DB_HOST,
    user: process.env.MYSQL_DB_USER,
    database: process.env.MYSQL_DB_NAME,
    password: process.env.MYSQL_DB_PASSWORD,
    port: 3306,
}

const pool = mysql.createPool(credentials);
let emoji_names: string[];

export async function check_user_auth(ctx: any, result: any) {

    let connection;

    try {
        // Get a connection from the pool
        connection = await pool.getConnection();
        
        const insertQuery = `
            SELECT * FROM users WHERE phone = ?;
        `;
        
        /* const insertQuery = `
            INSERT INTO users(username, password, phone) 
            VALUES (?, ?, ?);
        `; */

        // Execute the query with parameterized inputs
        const [rows] = await connection.execute(insertQuery, [
            ctx.from
        ]);

        /*
        Returned rows: [
  {
    id: 0,
    username: 'pedrobergaglio',
    password: 'password',
    phone: '5491131500591',
    created_at: 2024-08-21T19:23:24.000Z
  }
]
  
check len... etc*/

        console.log('Returned rows:', rows);

        // Return the inserted row (if needed)
        return rows;
    } catch (err) {
        console.error('Error inserting feedback:', err.message, 'emojis description:', emoji_names.join(', '));
    } finally {
        // Release the connection back to the pool
        if (connection) {
            connection.release();
        }
    }
}
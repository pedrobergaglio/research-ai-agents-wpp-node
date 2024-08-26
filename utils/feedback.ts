import { createBot, createProvider, createFlow, addKeyword, utils, EVENTS } from '@builderbot/bot'
import { MysqlAdapter as Database } from '@builderbot/database-mysql'
import { MetaProvider as Provider } from '@builderbot/provider-meta'
import mysql from 'mysql2/promise';
import * as fs from 'fs';
import csv from 'csv-parser';

export const emojiMap = await loadEmojiData('emoji_df.csv');

const credentials = {
    host: process.env.MYSQL_DB_HOST,
    user: process.env.MYSQL_DB_USER,
    database: process.env.MYSQL_DB_NAME,
    password: process.env.MYSQL_DB_PASSWORD,
    port: 3306,
}

interface EmojiData {
    emoji: string;
    name: string;
    group: string;
    sub_group: string;
    codepoints: string;
}

/**
 * Loads emoji data from a CSV file and returns a map of emoji codepoints to names.
 *
 * @param filePath - The path to the CSV file containing emoji data.
 * @returns A promise that resolves to a map of emoji codepoints to names.
 */
export function loadEmojiData(filePath: string): Promise<Map<string, string>> {
    return new Promise((resolve, reject) => {
        const emojiMap = new Map<string, string>();
        fs.createReadStream(filePath)
            .pipe(csv())
            .on('data', (row: EmojiData) => {
                emojiMap.set(row.codepoints.toLowerCase(), row.name);
            })
            .on('end', () => {
                resolve(emojiMap);
            })
            .on('error', (error) => {
                reject(error);
            });
    });
}


/**
 * Retrieves the names of emojis based on their code points from a CSV file.
 * @param emojiCodes - An array of emoji code points (e.g., '1F601').
 * @param filePath - The path to the CSV file containing emoji data.
 * @returns A promise that resolves to an array of emoji names in the same order as the input codes.
 */
export async function getEmojiNames(emojiCodes: string[]): Promise<string[]> {
    return emojiCodes.map(code => emojiMap.get(code) || null);
}

/**
 * Checks if a message contains only emojis and returns an array of clean code points if true.
 * @param message - The message string to check.
 * @returns An array of clean code points if the message contains only emojis, otherwise false.
 */
export function isOnlyEmojis(message: string): boolean | string[] {
    const emojiRegex = /^[\p{Emoji_Presentation}\p{Emoji}\uFE0F]+$/gu;
    const matchedEmojis = message.match(emojiRegex);

    if (matchedEmojis && matchedEmojis[0] === message) {
        return Array.from(message).map((char: string) => 
            char.codePointAt(0)?.toString(16)
        );
    }
    return false;
}

const pool = mysql.createPool(credentials);
let emoji_names: string[];

export async function insert_feedback(ctx: any, result: any) {
    emoji_names = await getEmojiNames(result);
    console.log('The user sent a reaction feedback that was saved in the database:', emoji_names);
    let connection;

    try {
        // Get a connection from the pool
        connection = await pool.getConnection();

        // Insert query with parameterized values
        const insertQuery = `
            INSERT INTO feedback_reactions (phone, emojis, context) 
            VALUES (?, ?, ?);
        `;

        // Execute the query with parameterized inputs
        const [rows] = await connection.execute(insertQuery, [
            ctx.from,
            emoji_names.join(', '), // Join emoji names as a string
            '' // Assuming context is empty for now
        ]);

        console.log('Feedback inserted:', rows);

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